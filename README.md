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
- UI 模式：标准库（Tkinter、argparse 等）
- Headless 训练模式：Ray RLlib + PettingZoo + Gymnasium

```bash
pip install "ray[rllib]==2.55.0" pettingzoo==1.25.0 gymnasium==1.2.3
```

## 快速开始

### 1）启动图形界面（默认）

```bash
python3 main.py
```

或显式指定：

```bash
python3 main.py --mode ui
```

加载 RLlib 训练检查点进行 UI 推理回放：

```bash
python3 main.py --mode ui --load-checkpoint /absolute/path/to/checkpoint
```

### 2）启动无界面课程训练（Ray RLlib）

```bash
python3 main.py --mode headless --preset stable --grid-size 25 --episodes 10 --ticks 300
```

检查点默认输出到：

```text
./checkpoints
```

## 完整训练使用指导（Headless + RLlib）

### 1）安装依赖

推荐使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirement.txt
```

> `tkinter` 为 Python 标准库组件（UI 模式依赖），通常无需通过 pip 额外安装。

### 2）确认命令行可用

```bash
python3 main.py --mode headless --help
```

如果这里报 `ModuleNotFoundError`，通常是依赖未安装完整，请重新执行 `pip install -r requirement.txt`。

### 3）先做一次最小训练冒烟

```bash
python3 main.py --mode headless \
  --preset stable \
  --grid-size 20 \
  --episodes 1 \
  --ticks 100 \
  --checkpoint-every 1
```

用途：快速确认训练流程、环境构建和检查点保存是否正常。

### 4）执行标准课程训练

```bash
python3 main.py --mode headless \
  --preset balanced \
  --grid-size 25 \
  --episodes 10 \
  --ticks 300 \
  --log-interval 1 \
  --checkpoint-every 5 \
  --checkpoint-dir ./checkpoints
```

训练将依次运行三个课程关卡：

- `level1_collect_and_survive`
- `level2_asymmetric_tracking`
- `level3_self_play_coevolution`

每个关卡结束会保存最终检查点，按 `--checkpoint-every` 还会保存中间检查点。

### 5）统计一致性验证（不训练）

```bash
python3 main.py --mode headless \
  --validate-statistics \
  --preset stable \
  --grid-size 25 \
  --ticks 300 \
  --alignment-runs 10 \
  --checkpoint-dir ./checkpoints
```

该模式用于比较旧核心与并行环境的统计结果，不执行 PPO 训练；报告输出为：

```text
./checkpoints/statistical_alignment_report.json
```

### 6）关键参数建议

- 快速调试：`--episodes 1~3 --ticks 50~150`
- 常规训练：`--episodes 10+ --ticks 300+`
- 更高稳定性：固定 `--seed`
- 无 GPU 环境：保持 `--num-gpus 0`

### 7）常见训练问题排查

- **缺少依赖（如 numpy / gymnasium / pettingzoo）**  
  重新执行 `pip install -r requirement.txt`
- **训练速度慢**  
  先减小 `--grid-size`、`--ticks`、`--episodes`
- **检查点未生成**  
  确认 `--checkpoint-every` 大于 0，且 `--checkpoint-dir` 目录可写

## 命令行参数说明

### 通用参数

- `--mode {ui,headless}`：运行模式（图形界面 / 无界面训练）

### 无界面模式参数（RLlib）

- `--preset {stable,balanced,intense}`：预设参数组
- `--grid-size`：网格大小（边长）
- `--ticks`：每轮最大环境步数
- `--episodes`：训练轮数（每轮调用一次 PPO train）
- `--seed`：随机种子
- `--log-interval`：日志输出间隔
- `--checkpoint-every`：每多少回合保存一次检查点（0 表示不保存）
- `--checkpoint-dir`：检查点输出目录
- `--framework`：RLlib 框架（当前为 torch）
- `--num-env-runners` / `--num-gpus`：RLlib 运行资源
- `--train-batch-size` / `--learning-rate` / `--gamma`：PPO 训练超参
- `--validate-statistics`：运行新旧引擎统计一致性验证（不训练）
- `--alignment-runs`：统计一致性验证重复次数

## 多智能体训练与 Action Mask

- Headless 训练使用 `ecosystem_env.py` 的 PettingZoo `ParallelEnv`。
- 通过 RLlib 多策略映射实现参数共享：
  - 所有 `rabbit_*` 共享 `rabbit_policy`
  - 所有 `fox_*` 共享 `fox_policy`
- 观测包含：
  - `grid`: `(4, 11, 11)`
  - `state`: `(3,)`
  - `action_mask`: `(6,)`，语义为 `1=合法, 0=非法`
- `action_mask` 屏蔽项包括：
  - 越界移动
  - 不可通行地形移动
  - 繁殖非法（未成年、能量不足、无可出生邻格、物种池已满）

## 新旧引擎对齐标准（统计一致）

- 不要求同 seed 下的轨迹级一致。
- 通过 `--validate-statistics` 运行统计对齐实验，输出：
  - 最终种群规模
  - 种群均值
  - 平均平衡度
  - 平均年龄
- 报告输出到：`checkpoints/statistical_alignment_report.json`

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
- `ecosystem_env.py`：PettingZoo ParallelEnv（当前唯一物理规则源）
- `ecosystem.py`：UI 兼容壳（适配到 `EcosystemEnv`）
- `ecosystem_core.py`：旧版核心（已标记为过渡期兼容，后续退役）
- `organisms.py`：生物行为（移动、觅食、繁殖、能量）
- `genetics.py`：基因参数与变异逻辑
- `terrain.py`：地形类型与地形生成
- `config.py`：季节系统与预设参数
- `headless_training.py`：RLlib 课程训练与统计一致性验证
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
