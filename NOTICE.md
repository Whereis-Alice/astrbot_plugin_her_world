# 来源与署名

## 上游项目

本仓库是下面这个项目的二次开发版（fork / derivative work）：

- 项目：`astrbot_plugin_virtual_world`（虚拟世界 VW）
- 作者：**exneverbur**
- 仓库：https://github.com/exneverbur/astrbot_plugin_virtual_world
- 本仓库的基线版本：上游 **v2.1.8**

世界地图、动作系统、日程、数值与情绪、记忆与通讯录、事件机制、网页编辑器这些核心设计
都来自原作者。本仓库从 v2.2.0 起在它的基础上继续开发，改动集中在：

1. 换名与标识符隔离（插件名 / 指令 / 数据目录 / 日志前缀 / 前端缓存键）；
2. 「从工具导入」批量把 AstrBot 工具挂成动作，以及动作库的筛选与批量管理；
3. 与其它插件的钩子桥接（表情包图片、TTS 语音、世界树上下文与临时模型）；
4. 首次启动时从原插件数据目录整份搬迁数据。

## 联动插件

下列插件由 [Whereis-Alice](https://github.com/Whereis-Alice) 维护，本插件只做了**兼容适配**，
没有复制它们的代码：

- https://github.com/Whereis-Alice/astrbot_plugin_meme_magpie
- https://github.com/Whereis-Alice/astrbot_plugin_worldtree_lore
- https://github.com/Whereis-Alice/astrbot_plugin_genie_tts_llm

## 许可说明

上游仓库当前**没有附带开源许可证文件**。因此本仓库同样不额外声明许可证：
它按上游同样的条件提供，一切权利与授权问题请以原作者为准。
如果你打算商用或再分发，请先与原作者（exneverbur）确认授权。

发现署名或来源有遗漏、或者你不希望自己的作品以这种方式被引用，请提 issue，我们会立刻处理。
