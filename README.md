# 生态系统模拟器（Ecosystem）

这是一个使用 Python + Tkinter 构建的生态系统仿真项目。你可以通过图形界面观察植物、草食动物、肉食动物在网格地图中的生存、繁殖、捕食与消亡过程，也可以使用无界面模式进行课程化训练并导出检查点。

## 这个项目是做什么的

本项目用于模拟一个离散网格世界中的生态演化过程，核心目标是：

- 观察多物种在资源有限条件下的动态变化
- 研究参数（繁殖率、能量阈值、寿命、网格大小等）对生态平衡的影响
- 支持可视化展示与无界面批量运行两种模式
- 支持导出历史数据，便于后续分析

## 主要功能

- 图形化配置面板：快速设置预设、网格尺寸、初始数量、总 Tick 数、速度
- 实时仿真面板：缩放、平移、暂停、单步、停止
- 实时统计与曲线：种群数量、平均年龄、平均能量、平衡度、趋势图
- 结果面板：最终统计、平衡评估、历史曲线、再次运行
- 数据导出：支持 CSV 和 JSON
- 无界面课程训练：支持多关卡循环、日志输出、检查点保存

## 运行环境

- Python 3.10 及以上
- 依赖均为标准库（Tkinter、argparse 等），通常无需额外安装包

## 快速开始

### 1）启动图形界面（默认）

```bash
python3 main.py
```

或显式指定：

```bash
python3 main.py --mode ui
```

### 2）启动无界面课程训练

```bash
python3 main.py --mode headless --api-version v1 --preset stable --grid-size 25 --episodes 10 --ticks 300
```

检查点默认输出到：

```text
./checkpoints
```

## 命令行参数说明

### 通用参数

- `--mode {ui,headless}`：运行模式（图形界面 / 无界面训练）

### 无界面模式参数

- `--preset {stable,balanced,intense}`：预设参数组
- `--api-version {v1,v2}`：环境接口版本（默认 v1；v2 启用奖励塑形/性状观测增强）
- `--grid-size`：网格大小（边长）
- `--ticks`：每回合最大 Tick 数
- `--episodes`：训练回合数
- `--seed`：随机种子
- `--observation-radius`：观察半径
- `--log-interval`：日志输出间隔
- `--checkpoint-every`：每多少回合保存一次检查点（0 表示不保存）
- `--checkpoint-dir`：检查点输出目录
- `--living-penalty`：每 Tick 生存惩罚（可覆盖 v2 默认）
- `--energy-delta-scale`：正向能量变化奖励系数（可覆盖 v2 默认）
- `--reproduction-reward`：繁殖成功奖励（可覆盖 v2 默认）
- `--collision-penalty`：碰撞惩罚（可覆盖 v2 默认）
- `--death-penalty-starvation` / `--death-penalty-predation` / `--death-penalty-old-age`：按死亡原因设置惩罚
- `--reward-breakdown-agents`：在 info 中输出按 agent 的奖励分解明细（默认仅输出总分解）

## v1 / v2 兼容说明

- `v1`（默认）：
  - 保持原有观测结构：`obs["agents"][agent_id]` 为局部张量。
  - 保持原有奖励行为与字段，适配现有训练脚本。
- `v2`：
  - 引入奖励塑形：生存惩罚、energy delta 奖励、按死亡原因惩罚、奖励分解日志。
  - 引入性状驱动：新增 `diet` 基因（`<0.5` 偏植食，`>=0.5` 偏肉食）。
  - 引入亲缘识别：局部观测新增 kinship 通道。
  - 引入内部驱动：`scalar_state = [energy_norm, age_norm, hunger_drive, reproduction_urge, fear_drive]`。
  - 观测窗口大小由 `--observation-radius` 决定：`(2r+1) x (2r+1)`（例如 `r=5` 对应 `11x11`）。

## 图形界面怎么使用

### 配置页

1. 选择主题（自然 / 暗色 / 亮色）
2. 选择预设（稳定 / 均衡 / 激烈）
3. 调整参数（网格尺寸、总 Tick、延迟、各类生物初始数量）
4. 点击“开始模拟”

### 模拟页

- 鼠标滚轮：缩放
- 右键/中键拖拽：平移
- 左键双击：重置视图
- 底部控制条：暂停 / 单步 / 停止 / 调速
- 右侧抽屉：查看详细统计与种群历史曲线

### 结果页

- 查看最终统计与生态平衡评分
- 导出 CSV / JSON
- 返回配置页或使用相同参数重新运行

## 数据导出说明

- CSV：导出植物、草食动物、肉食动物的历史数量序列
- JSON：导出历史数量 + 模拟元数据（网格大小、初始数量、预设等）

## 代码结构（核心文件）

- `main.py`：程序入口与命令行参数解析
- `game_ui.py`：应用主流程（配置页 → 模拟页 → 结果页）
- `ecosystem_core.py`：无 Tk 依赖的核心环境逻辑（reset/step/render）
- `ecosystem.py`：兼容适配层
- `organisms.py`：生物行为（移动、觅食、繁殖、能量）
- `genetics.py`：基因参数与变异逻辑
- `terrain.py`：地形类型与地形生成
- `config.py`：季节系统与预设参数
- `headless_training.py`：无界面课程训练与检查点保存
- `ui_config_panel.py`：配置面板
- `ui_simulation_panel.py`：仿真面板
- `ui_result_panel.py`：结果面板
- `ui_overlay.py`、`ui_widgets.py`：悬浮层与图表组件
- `data_exporter.py`：CSV/JSON 导出

## 预设说明

- `stable`：稳定共存，适合观察长期平衡
- `balanced`：捕食压力适中，波动相对平衡
- `intense`：竞争更激烈，种群波动更明显

## 常见问题

- **无法开始模拟 / 弹出“配置无效”**：生物总数超过网格容量，请减少初始数量或增大网格。
- **想快速验证是否可运行**：先执行 `python3 main.py --help`，再执行一次短回合 headless 命令。

---

如果你想继续扩展本项目，建议优先从 `config.py`（参数）、`organisms.py`（行为规则）、`ui_*`（展示与交互）三个方向入手。
