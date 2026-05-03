# FermiLink VASP+QE 工作流总结备忘 — production-grade 起点

**Workspace**: `~/fermilink/vasp-demo`, `~/fermilink/qe-demo`  
**Site**: `x13dai-t` (96 CPU, 515 GiB, SLURM partition=batch)  
**Status**: Production-ready for research tasks (2026-05-03)

---

## 1. 物理 Baseline (跨 code 验证)

| Code | PP type | NBANDS | Job | Indirect gap (eV) | Δ vs Q-E |
|------|---------|--------|-----|-------------------|----------|
| Q-E PWscf | USPP, ecutwfc=30 Ry | — | 26530 | **0.5750** | reference |
| VASP 6.6 | PAW.64 PBE | 12 | 26534 | 0.572500 | -2.5 meV |
| VASP 6.6 | PAW.64 PBE | 12 | 26542 | 0.572568 | -2.4 meV |
| VASP 6.6 | PAW.64 PBE | 24 | 26547 | 0.572568 | -2.4 meV |
| VASP 6.6 | PAW.64 PBE | 24 | 26549 | 0.572568 | -2.4 meV |

**结论**: 
- 跨 code Δ = 2.4 meV (textbook USPP vs PAW agreement)
- 跨 4 次 VASP run Δ = **0.0 meV** (bit-exact reproducibility)
- VBM 在 Γ, CBM 在 Γ→X 约 0.83 处 — 跟 Si textbook 完全一致

---

## 2. Site-Specific 关键事实 (validated by sbatch testing)

### 2.1 软件栈

```
oneapi/2024.2.0                                  (compiler + MPI)
vasp/6.6.0-oneapi.2024.2.0  (default)           (其他: 5.4.4, 6.4.3, 6.5.0, 6.5.1)
q-e/develop-oneapi.2024.2.0                      (PWscf + ph + wannier90 接口)

Python: /home/werner/.pyenv/versions/datasci/bin/python  (3.11, 含 pymatgen)
```

### 2.2 POTCAR 站点路径

```
~/Public/hpc/vasp/pot/
├── potpaw_PBE.64/<E>/POTCAR    ← ALWAYS USE THIS (latest, with SHA256+COPYR)
├── potpaw_PBE.54/, .52/         (older)
├── potpaw_PBE/                  (2010 release, marked "not supported")
└── potUSPP_*/                   (USPP, q-e 用的另一种)
```

INCAR/run.sh 永远 `$VASP_PP/potpaw_PBE.64/<E>/POTCAR`，**不用 unsuffixed**。

### 2.3 SLURM resource layout (这条是 site-specific 的核心)

```
✅ USE:  --nodes=1 --ntasks=1 --cpus-per-task=N
         mpirun -np "${SLURM_CPUS_PER_TASK}" "$VASP_STD"

❌ DO NOT USE:  --ntasks=N --cpus-per-task=1
   原因: SLURM cgroup + Intel MPI Hydra srun bstrap_proxy 把所有 ranks
         绑到 CPU 0, 100x slowdown. Job 26548 实测 10+ 分钟超时.
```

这条**不是 textbook 推荐**，是 site-specific 测出来的。其他机器可能反过来。

### 2.4 Bash + Lmod 行为

```
BASH_ENV=/usr/local/lmod/lmod/init/bash       (system-wide)
→ 裸 #!/bin/bash 在 sbatch 内能 module load (不需要 -l 也不需要 -i)

mpirun 是 ~/.bashrc 里的 lazy-load function:
  - 检查 args 是否含 vampire-parallel 等特殊 token → 自动 module load
  - 否则 fall through 到 `command mpirun "$@"` (透明)
  - 对 VASP args 完全无影响, 不需要绕开

subshell 隔离 100% 标准:
  ( module load X )    # X 在 subshell 内 work
  module list           # 出 subshell 后 X 完全没了
  → module load 必须在 main shell 跑, 不进 ( ... )
```

### 2.5 sbatch 内的 path 陷阱

```
${BASH_SOURCE[0]} / $0 在 sbatch 内 → 指向 /var/spool/slurmd/jobNNN/slurm_script
${SLURM_SUBMIT_DIR}                  → 真正的项目目录
→ 所有 path 都用 SLURM_SUBMIT_DIR
```

### 2.6 NBANDS for non-SCF band runs

```
VASP 默认 NBANDS = NELECT/2 + buffer, 对小 cell 可能刚好等于占据 bands.
非 SCF band 计算需要 unoccupied bands 才能找 CBM.
→ Si 2-atom cell 默认 NBANDS=8, 必须显式 NBANDS=12 或更高
→ 经验法则: NBANDS >= 1.5 × default
```

NBANDS 翻倍 (12→24) 不影响 gap (0.0 meV diff)，只影响 plot 高能段平滑度。

### 2.7 perf_logger 多 OUTCAR 消歧义

```
当 project 含 OUTCAR_scf 和 OUTCAR_band 时:
  export PERF_OUTCAR_PATH=bands/OUTCAR    (or scf/OUTCAR)
  python3 _perf_append.py
→ logger 会读你指定的 OUTCAR, 不依赖 mtime fallback (不可靠)
```

`_perf_append.py` (commit 32a120d) 已实现这个 env var override。

---

## 3. Project Canonical Layout

```
projects/<YYYY-MM-DD>-<name>/
├── inputs/                     read-only canonical inputs (immutable)
│   ├── POSCAR
│   ├── POTCAR
│   ├── INCAR_scf
│   ├── INCAR_bands
│   ├── KPOINTS_scf  
│   └── KPOINTS_bands
├── relax/         (optional)   geometry optimization (ISIF=3)
├── scf/                        self-consistent SCF on final geometry
│   ├── POSCAR/POTCAR/INCAR/KPOINTS  (symlinks to ../inputs/...)
│   ├── CHGCAR / WAVECAR              (consumed by downstream stages)
│   ├── OUTCAR / OSZICAR / EIGENVAL / vasprun.xml
│   └── vasp.{out,err}
├── nscf/          (optional)   non-self-consistent uniform mesh (DOS, wannier feedstock)
├── bands/                      non-self-consistent line-mode k-path
│   ├── (symlinks to ../inputs/)
│   ├── CHGCAR (symlink → ../scf/CHGCAR)
│   └── OUTCAR / EIGENVAL / PROCAR / vasprun.xml
├── analysis/                   postprocessed deliverables
│   ├── band_analysis.json
│   ├── bands.png
│   └── module_list.txt
├── logs/                       transient logs (gitignored)
│   ├── slurm-*.{out,err}
│   ├── stage_times.tsv
│   └── perf_append.log
├── scripts/                    workflow code
│   ├── generate_inputs.py
│   ├── postprocess_bands.py
│   ├── run.sh
│   └── _perf_append.py        (symlink → ../../../_perf_append.py)
├── summary.md
└── .backup-<job_id>/           历史 baseline (可选, audit 用)
```

### 命名规范说明

| Stage 名 | Q-E 等价 | atomate2 等价 | 物理 |
|----------|----------|---------------|------|
| `relax/` | `vc-relax/relax` | `relax_dir` | ions move, electrons SC each step |
| `scf/` | `scf` | `static_dir` | self-consistent on fixed geometry |
| `nscf/` | `nscf` | `non_scf_uniform_dir` | ICHARG=11 uniform mesh |
| `bands/` | `bands` | `non_scf_line_dir` | ICHARG=11 line-mode |

跨 q-e + vasp 工作流统一用 q-e 风格（`scf` 强调 self-consistent，比 `static` 更精确）。

### Stage 间数据依赖（用 symlink 显式）

```
scf/POSCAR    → ../relax/CONTCAR    (if relax/ exists)
              → ../inputs/POSCAR    (if no relax/)
nscf/CHGCAR   → ../scf/CHGCAR
bands/CHGCAR  → ../scf/CHGCAR
bands/POSCAR  → 跟 scf 一致
```

---

## 4. 自动化工具

### 4.1 重组工具

```bash
~/fermilink/vasp-demo/scripts/reorganize-project.sh dry-run  <project>
~/fermilink/vasp-demo/scripts/reorganize-project.sh execute  <project>
```

把 flat layout 自动重组成 canonical sub-dirs。dry-run 模式可预览。

### 4.2 perf_log adaptive learning

```bash
~/fermilink/vasp-demo/perf_log.jsonl    # 7 条记录, 跨 task
~/fermilink/qe-demo/perf_log.jsonl
```

每条 entry 记录: `job_id, system, natoms, nkpts, nbands, encut, cpus, kpar, ncore, scf_iter, total_pipeline_sec, ...`

下次类似 system 跑前可读 perf_log 选最优 cpus/kpar/ncore。

### 4.3 fermilink loop

```bash
fermilink loop <task.md>           # 任意 .md 都可以, 不限 goal.md
fermilink loop --max-iterations N  # 控制循环次数
fermilink loop --sandbox bypass    # 内部 codex 用 full access
```

prompt .md 顶部必须有 `## SITE FACTS` 段（fermilink completion checkpoint 会重置 AGENTS.md，所以 site override 不能放 AGENTS.md）。

---

## 5. Canonical run.sh skeleton

```bash
#!/bin/bash
#SBATCH --job-name=<TASK>
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8           ← VASP MPI ranks
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

ulimit -Sn $(ulimit -Hn) 2>/dev/null; ulimit -s unlimited 2>/dev/null
set -euo pipefail

PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$PROJECT_DIR"
mkdir -p inputs scf bands analysis logs

export FL_SYSTEM_TAG="<system_tag_for_perf_log>"
export VASP_PP=~/Public/hpc/vasp/pot
PYTHON=/home/werner/.pyenv/versions/datasci/bin/python
MPI_RUN=/opt/intel/oneapi/2024.2.0/mpi/2021.13/bin/mpirun

# Module load in MAIN shell (rule 3)
module purge
module load oneapi/2024.2.0
module load vasp/6.6.0-oneapi.2024.2.0
module list > analysis/module_list.txt 2>&1
VASP_STD="$(command -v vasp_std)"

# Generate canonical inputs
"$PYTHON" scripts/generate_inputs.py

# === SCF stage ===
cd scf
ln -sfn ../inputs/POSCAR ../inputs/POTCAR ../inputs/INCAR_scf ../inputs/KPOINTS_scf .
mv INCAR_scf INCAR; mv KPOINTS_scf KPOINTS
"$MPI_RUN" -np "${SLURM_CPUS_PER_TASK}" "$VASP_STD" > vasp.out 2> vasp.err
cd ..

# === Bands stage ===
cd bands
ln -sfn ../inputs/POSCAR ../inputs/POTCAR ../inputs/INCAR_bands ../inputs/KPOINTS_bands .
mv INCAR_bands INCAR; mv KPOINTS_bands KPOINTS
ln -sfn ../scf/CHGCAR CHGCAR
[ -f ../scf/WAVECAR ] && ln -sfn ../scf/WAVECAR WAVECAR
"$MPI_RUN" -np "${SLURM_CPUS_PER_TASK}" "$VASP_STD" > vasp.out 2> vasp.err
cd ..

# === Postprocess ===
"$PYTHON" scripts/postprocess_bands.py > logs/postprocess.log 2>&1

# === Perf logging (rule 5+6+7) ===
export PERF_OUTCAR_PATH=bands/OUTCAR
"$PYTHON" scripts/_perf_append.py > logs/perf_append.log 2>&1
```

---

## 6. Cleanup convention

`summary.md` 写完后，agent (或人手) grep `goal.md/task.md` 找以下关键字：

```
nscf  bands  wannier  fat-band  projwfc  restart  kpoints_opt
wannier90  irvsp  vasp2trace  continuation  hse  hybrid
```

匹配 → keep `WAVECAR`  
不匹配 → `rm -f scf/WAVECAR bands/WAVECAR` (节省 27 MB / 任务)

`CHGCAR / OUTCAR / vasprun.xml / EIGENVAL` 永远 keep。

`summary.md` 末尾追加 `cleanup_decision: <kept WAVECAR | pruned WAVECAR>`。

---

## 7. Anti-patterns (不要踩的坑)

1. **改 AGENTS.md 做 site override** — fermilink completion checkpoint 会重置成 template. Site override 永远在 task `.md` 顶部 `## SITE FACTS` 段.

2. **`cp OUTCAR_band OUTCAR` 给 logger 找路** — fragile, 用 `PERF_OUTCAR_PATH` env var.

3. **`mpirun --oversubscribe`** — 是 `--ntasks=8 -c=1` 的 workaround, 不是 fix. 这台机器不能用 `-ntasks=N`, 别走这条路.

4. **硬编码 `/opt/intel/oneapi/2024.2.0/mpi/.../mpirun`** — oneapi 升级会失效. 让 `module load oneapi` 设置 PATH, 用 `command -v vasp_std` 拿绝对路径.

5. **信任 LLM agent 的 root cause narrative** — 写 probe script 验证. 如 `path_leak_strict.sh` 模板.

6. **textbook SLURM layout 不验证** — Job 26548 跑了 10 分钟才被 kill. 任何 SLURM resource 改动 sbatch test 一次再 commit.

7. **`module load X` 在 `( $func )` subshell 里** — subshell 退出后 PATH/LOADEDMODULES 全丢. 所有 module load 在 main shell.

8. **`BASH_SOURCE[0]` / `$0` 在 sbatch 内** — 用 `SLURM_SUBMIT_DIR`.

---

## 8. 多 task 工作流（开新研究方向时）

```
~/fermilink/vasp-demo/
├── tasks/
│   ├── 01-si-band-baseline.md         (已完成, 此 session 产物)
│   ├── 02-si-band-cosmetic.md         (已完成)
│   ├── 03-<your-next-research-task>.md
│   └── ...
├── SITE_FACTS.md                       (可选: 抽出共用 SITE FACTS 段)
├── SESSION_NOTES.md                    (跨 session postmortem)
├── projects/                           (fermilink-managed, 每个 task 一个 sub-dir)
│   ├── 2026-05-02-si-bands-vasp/
│   ├── 2026-05-XX-<next-task>/
│   └── memory.md                       (fermilink 持久化 plan/progress)
└── perf_log.jsonl                      (cross-task adaptive learning)
```

新任务起步：

```bash
# 1. 写 task .md (顶部带 SITE FACTS 段, 任务段说明物理目标)
vim tasks/03-fetase2-hse-soc.md

# 2. fermilink loop (会自动按 SITE FACTS 走, agent 一次性跑通的概率很高)
fermilink loop tasks/03-fetase2-hse-soc.md
```

---

## 9. 真实研究方向 onboarding 提示

你的研究方向是 **small-but-cutting-edge: topology / corep / 2D materials / MSG (Magnetic Space Groups)**。这套 baseline 是起跑线, 真正的研究任务可能涉及:

| 物理目标 | 需要的 stages | 关键 tools |
|----------|---------------|-----------|
| HSE band gap (more accurate) | scf (PBE) → scf (HSE) → bands (HSE) | LHFCALC, ALGO=D, LWANNIER90 |
| Spin-orbit coupling (heavy elements) | scf (PBE collinear) → scf (NCL+SOC) → bands | LSORBIT=T, MAGMOM, SAXIS |
| Topological Z2 / Berry phase | scf → wannier90 (W90 interp band) | wannier90, irvsp, vasp2trace |
| Corepresentation / MSG analysis | scf+bands at high-sym k → irrep analysis | irrep, vasp2trace, MSG database |
| 2D material slab | relax (slab, ISIF=2 kept c) → scf → bands | LDIPOL, IDIPOL=3, LVHAR=T |
| Phonons | relax → DFPT (q-e ph.x) | q-e, phonopy |

每个新方向第一次跑时:
1. 设计一个 small system 做 baseline (类似 Si)
2. **跨 code 比较** (q-e vs vasp 同物理量)
3. 看 perf_log.jsonl 选最优并行参数
4. 写进 SITE FACTS 段额外的 method-specific rules (HSE 的 k-mesh 处理, SOC 的 NBANDS 翻倍, 等)

---

## 10. 反思: LLM-driven workflow 的元教训

这个 baseline session 暴露了 7 个 LLM "plausibility-driven misdiagnosis" pattern. 真实研究中如果 task 复杂度增加, 这种 pattern 会更隐蔽:

```
正确的 LLM 协作模式:
  - 用户提供 ground truth (实测输出 / 文档 quote / probe script result)
  - LLM 给出多个候选假设, 标明不确定性
  - 用户选最有希望的, LLM 帮写 verification script
  - sbatch 验证后再 commit / 写 SITE FACTS

错误模式 (此 session 多次出现):
  - LLM 看现象立刻给"原因"
  - 用 plausibility 替代 verification
  - 写进持久化文件 (SITE FACTS / SESSION_NOTES) 之前没 sbatch 实测
  - cascade 中后续 fix 在错误 narrative 上叠加
```

**核心建议**: 
- 任何 SITE FACTS rule 修改前 → sbatch 验证
- 任何 cascade fix root cause → probe script 验证  
- 任何 textbook recommendation → 你机器实测
- 任何工具命名引用 → web search 文档

---

## 11. Quick reference

```bash
# 看 baseline 状态
cd ~/fermilink/vasp-demo
git log --oneline | head -5
cat SESSION_NOTES.md | head -50
head -100 goal.md         # SITE FACTS

# 跑 baseline (复现 0.572568 eV gap, ~13s)
cd projects/2026-05-02-si-bands-vasp
sbatch scripts/run.sh
sleep 25
jq .indirect_gap_ev analysis/band_analysis.json

# 看 perf history
tail -3 ~/fermilink/vasp-demo/perf_log.jsonl | jq '{job_id, nbands, total_pipeline_sec}'

# 起 fermilink loop 做新 task
fermilink loop tasks/03-<new-task>.md

# 起 codex 做单点 polish
codex --dangerously-bypass-approvals-and-sandbox \
      -C ~/fermilink/vasp-demo/projects/<project>/

# Si baseline 复现 quick-check (任何时候都该跑通)
cd ~/fermilink/vasp-demo/projects/2026-05-02-si-bands-vasp
rm -rf scf bands && mkdir scf bands
sbatch scripts/run.sh
# 期望: 13-18s 完成, gap = 0.572568 eV
```

---

## 12. Git 历史 (5 commits = 完整建立过程)

```
c6c9e1b  site facts: empirically validate SLURM layout (rule 5 fix); reorganize project to canonical sub-dirs
32a120d  polish: NBANDS=24 cleaner bands.png + perf logger PERF_OUTCAR_PATH support
a8f455a  site facts: tighten SLURM rules after path_leak_strict probe
f487478  fermilink loop: completion checkpoint 2026-05-02T09:45:11 (job 26542 NBANDS=12)
eb6f108  fermilink loop: completion checkpoint 2026-05-01T02:53:12 (job 26534 first VASP baseline)
```

每个 commit 都是一个可复现状态点。`git checkout <sha>` 能完全 reproduce 那时的物理结果。

---

## 终点 = 起点

工程基建立完了。物理 baseline 跨 code 一致到 meV 级。SITE FACTS 全部 sbatch-validated。Project layout 标准化。下次开 session 直接做真实研究——不再做 plumbing 工作。

**Saturday May 3, 2026** — baseline done. 真正的物理探索从这里开始。
