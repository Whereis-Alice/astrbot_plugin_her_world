"""接管回复与其它插件联动的回归测试。

覆盖三条真实存在的联动线：

- 表情包插件（meme_magpie）：在 ``on_decorating_result`` 里往消息链塞图片；
- 语音插件（genie_tts）：在 ``on_llm_response`` 里把回复换成一段语音；
- 世界树（worldtree_lore）：往 ``system_prompt`` / ``extra_user_content_parts``
  写设定，并用 ``selected_provider`` 临时换模型。

共同点是：本插件接管回复时是自己调模型、自己发送的，AstrBot 的那条管线不会跑，
所以这些钩子必须由本插件补发，而且**钩子产出的东西不能被丢掉**。
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN_DIR)
sys.path.insert(0, HERE)

import fake_astrbot  # noqa: E402

fake_astrbot.install()

_TMP_DIR = tempfile.mkdtemp(prefix="her-world-bridge-")
os.environ["HER_WORLD_DATA_DIR"] = _TMP_DIR


def load_plugin_module():
    if "hw_bridge_plugin" in sys.modules:
        return sys.modules["hw_bridge_plugin"]
    spec = importlib.util.spec_from_file_location(
        "hw_bridge_plugin",
        os.path.join(PLUGIN_DIR, "main.py"),
        submodule_search_locations=[PLUGIN_DIR],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["hw_bridge_plugin"] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_plugin_module()


class _Plain:
    def __init__(self, text: str = "") -> None:
        self.text = text


class _Image:
    """图片段（表情包插件塞进来的那种）。"""

    def __init__(self, file: str = "") -> None:
        self.file = file


class _Record:
    """语音段（TTS 插件塞进来的那种）。"""

    def __init__(self, file: str = "") -> None:
        self.file = file


class _Chain:
    def __init__(self, chain: list | None = None) -> None:
        self.chain = list(chain or [])


class _Result:
    def __init__(self) -> None:
        self.chain: list = []

    def message(self, text: str) -> "_Result":
        self.chain.append(_Plain(text))
        return self

    def set_result_content_type(self, _typ) -> "_Result":
        return self


class _Event:
    def __init__(self) -> None:
        self.unified_msg_origin = "aiocqhttp:GroupMessage:1"
        self._result = None
        self.sent: list = []

    def get_result(self):
        return self._result

    def set_result(self, result) -> None:
        self._result = result

    def clear_result(self) -> None:
        self._result = None

    def get_message_str(self) -> str:
        return "在吗"

    def get_extra(self, key: str, default=None):
        return default

    async def send(self, chain) -> None:
        self.sent.append(chain)


def install_hook_stubs(*, on_response=None, on_decorating=None) -> None:
    """装一套够用的 AstrBot 回复钩子桩，可注入两个钩子的行为。"""

    core = types.ModuleType("astrbot.core")
    pipeline = types.ModuleType("astrbot.core.pipeline")
    context_utils = types.ModuleType("astrbot.core.pipeline.context_utils")

    async def call_event_hook(event, hook_type, *args, **kwargs):
        if hook_type == "llm_response" and on_response is not None:
            await on_response(event, args[0] if args else None)
        if hook_type == "decorating_result" and on_decorating is not None:
            await on_decorating(event)
        return False

    context_utils.call_event_hook = call_event_hook

    provider = types.ModuleType("astrbot.core.provider")
    entities = types.ModuleType("astrbot.core.provider.entities")

    class LLMResponse:
        def __init__(self, role: str = "", completion_text: str = "", **_kwargs) -> None:
            self.role = role
            self.completion_text = completion_text
            self.result_chain = None

    entities.LLMResponse = LLMResponse

    star = types.ModuleType("astrbot.core.star")
    star_handler = types.ModuleType("astrbot.core.star.star_handler")

    class EventType:
        OnLLMResponseEvent = "llm_response"
        OnDecoratingResultEvent = "decorating_result"

    star_handler.EventType = EventType

    message = types.ModuleType("astrbot.core.message")
    result_module = types.ModuleType("astrbot.core.message.message_event_result")

    class ResultContentType:
        LLM_RESULT = "llm_result"

    result_module.MessageEventResult = _Result
    result_module.ResultContentType = ResultContentType

    sys.modules.update(
        {
            "astrbot.core": core,
            "astrbot.core.pipeline": pipeline,
            "astrbot.core.pipeline.context_utils": context_utils,
            "astrbot.core.provider": provider,
            "astrbot.core.provider.entities": entities,
            "astrbot.core.star": star,
            "astrbot.core.star.star_handler": star_handler,
            "astrbot.core.message": message,
            "astrbot.core.message.message_event_result": result_module,
        }
    )


class BridgeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = MODULE

    def setUp(self) -> None:
        # 桥接里判断 Plain 用的是模块里那份，换成本文件的替身
        self._plain = self.module.Plain
        self.module.Plain = _Plain

    def tearDown(self) -> None:
        self.module.Plain = self._plain

    def _plugin(self):
        return self.module.HerWorldPlugin(
            self.module.Context(),
            self.module.AstrBotConfig({"enabled": True, "tick_interval": 60}),
        )


class ReplyChainTests(BridgeCase):
    def test_meme_image_from_decorating_hook_is_kept(self):
        """表情包插件在发送前钩子里塞的图不能被吞掉。"""

        plugin = self._plugin()
        image = _Image("meme.png")

        async def add_image(event):
            result = event.get_result()
            if result is not None:
                result.chain.append(image)

        install_hook_stubs(on_decorating=add_image)
        try:
            messages, extra = asyncio.run(
                plugin._bridge_reply_hooks(_Event(), ["今天也要加油哦"])
            )
        finally:
            plugin.db.raw.close()
        self.assertEqual(messages, ["今天也要加油哦"])
        self.assertEqual(extra, [image])

    def test_tts_audio_replaces_text(self):
        """语音插件把整条回复换成语音时，正文不该再发一遍。"""

        plugin = self._plugin()
        record = _Record("voice.silk")

        async def replace_with_audio(_event, response):
            response.result_chain = _Chain([record])

        install_hook_stubs(on_response=replace_with_audio)
        try:
            messages, extra = asyncio.run(
                plugin._bridge_reply_hooks(_Event(), ["我在这儿呢"])
            )
        finally:
            plugin.db.raw.close()
        self.assertEqual(messages, [])
        self.assertEqual(extra, [record])

    def test_tts_audio_keeps_text_when_plugin_keeps_it(self):
        """插件同时给了文本和语音（audio_and_text 模式）时，两样都发。"""

        plugin = self._plugin()
        record = _Record("voice.silk")

        async def add_audio(_event, response):
            response.result_chain = _Chain([_Plain("我在这儿呢"), record])

        install_hook_stubs(on_response=add_audio)
        try:
            messages, extra = asyncio.run(
                plugin._bridge_reply_hooks(_Event(), ["我在这儿呢"])
            )
        finally:
            plugin.db.raw.close()
        self.assertEqual(messages, ["我在这儿呢"])
        self.assertEqual(extra, [record])


class SendExtraTests(BridgeCase):
    def test_extra_components_ride_with_last_message(self):
        plugin = self._plugin()
        image = _Image("meme.png")
        event = _Event()
        try:
            asyncio.run(
                plugin._send_reply(
                    event, ["第一句", "第二句"], extra_chain=[image]
                )
            )
        finally:
            plugin.db.raw.close()
        self.assertEqual(len(event.sent), 2)
        first, second = event.sent
        self.assertEqual([type(item).__name__ for item in first.chain], ["_Plain"])
        self.assertEqual(
            [type(item).__name__ for item in second.chain], ["_Plain", "_Image"]
        )

    def test_extra_components_only_send_one_message(self):
        plugin = self._plugin()
        record = _Record("voice.silk")
        event = _Event()
        try:
            asyncio.run(plugin._send_reply(event, [], extra_chain=[record]))
        finally:
            plugin.db.raw.close()
        self.assertEqual(len(event.sent), 1)
        self.assertEqual([type(item).__name__ for item in event.sent[0].chain], ["_Record"])

    def test_nothing_to_send_is_a_noop(self):
        plugin = self._plugin()
        event = _Event()
        try:
            asyncio.run(plugin._send_reply(event, []))
        finally:
            plugin.db.raw.close()
        self.assertEqual(event.sent, [])


class RequestContextTests(BridgeCase):
    def test_extra_user_content_parts_are_merged(self):
        """世界树写进 extra_user_content_parts 的设定要跟着她这一轮走。"""

        part = types.SimpleNamespace(text="【设定】她住在一座靠海的小城。")
        req = types.SimpleNamespace(
            extra_user_content_parts=[part, types.SimpleNamespace(text="")],
        )
        # 调用方传入的是**摘掉人格之后**的 system_prompt，这里照着它的约定走
        merged = self.module._merged_request_context(req, "别的插件写的上下文")
        self.assertIn("别的插件写的上下文", merged)
        self.assertIn("靠海的小城", merged)
        self.assertEqual(
            merged.splitlines()[0], "别的插件写的上下文"
        )

    def test_missing_extra_parts_is_fine(self):
        req = types.SimpleNamespace(system_prompt="只有系统提示词")
        self.assertEqual(self.module._merged_request_context(req, "只有系统提示词"), "只有系统提示词")
        self.assertEqual(self.module._merged_request_context(types.SimpleNamespace()), "")


class TurnProviderTests(BridgeCase):
    def test_selected_provider_is_used_for_main_call(self):
        """别的插件临时指定的模型，本插件接管时也要用。"""

        plugin = self._plugin()
        calls: list[str] = []

        async def fake_generate(**kwargs):
            calls.append(str(kwargs.get("chat_provider_id") or ""))

            class _Response:
                completion_text = "好"

            return _Response()

        plugin.context.llm_generate = fake_generate

        class _PickerEvent(_Event):
            def get_extra(self, key: str, default=None):
                if key == "selected_provider":
                    return "worldtree-model"
                return default

        async def run() -> None:
            token = plugin.context
            self.assertEqual(plugin.turn_provider_override("s1"), "")
            async with plugin._reply_turn_provider("s1", _PickerEvent()):
                self.assertEqual(plugin.turn_provider_override("s1"), "worldtree-model")
                await plugin.engine.llm.generate(
                    session_id="s1", system_prompt="", prompt="你好"
                )
            self.assertEqual(plugin.turn_provider_override("s1"), "")
            self.assertIs(token, plugin.context)

        try:
            asyncio.run(run())
        finally:
            plugin.db.raw.close()
        self.assertEqual(calls, ["worldtree-model"])

    def test_explicit_plugin_provider_wins_over_turn_hint(self):
        plugin = self._plugin()
        plugin.llm_provider_id = "配置里选的模型"
        calls: list[str] = []

        async def fake_generate(**kwargs):
            calls.append(str(kwargs.get("chat_provider_id") or ""))

            class _Response:
                completion_text = "好"

            return _Response()

        plugin.context.llm_generate = fake_generate

        async def run() -> None:
            async with plugin._reply_turn_provider("s1", _Event()):
                plugin._turn_provider_overrides["s1"] = "worldtree-model"
                await plugin.engine.llm.generate(
                    session_id="s1", system_prompt="", prompt="你好"
                )

        try:
            asyncio.run(run())
        finally:
            plugin.db.raw.close()
        self.assertEqual(calls, ["配置里选的模型"])


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()
