# specs/prompts/ · 8 派 LLM Prompt 结构化契约

> **目的**:把 `knowledge/20-v2-prompts/*.md` 的"人类可读叙事"转化为"机器可加载"的 YAML 契约
> **状态**:v1.0.0(2026-07-10 启动)
> **关系**:**不取代** 20-v2-prompts/*.md,而是给它们一个结构化入口

## 与现有文档的关系

| 现有文档 | 角色 | specs/prompts/ 镜像 |
|---|---|---|
| `knowledge/20-v2-prompts/bazi.md` | 八字 prompt 叙事文档 | → `specs/prompts/bazi.yaml` |
| `knowledge/20-v2-prompts/tarot.md` | 塔罗 prompt 叙事 | → `specs/prompts/tarot.yaml` |
| ... 8 派全部 | ... | → 8 个 YAML |

## 通用结构(所有 8 派)

每个 YAML 都遵循同一套字段:

```yaml
liupai: <流派 id>
version: '1.0.0'           # spec 版本(配合 schema_version)
output_schema_ref: ../schools/<liupai>.result.schema.json  # 期望输出

role: |                      # LLM 人设(1-3 句话)
  你是一位...

context:                     # 通用上下文变量(8 派都包含)
  - { key: gender,     label: 用户性别 }
  - { key: question,   label: 用户问题 }
  - { key: tst,        label: 真太阳时(经度+EoT 校正) }
  - { key: city,       label: 出生地(可选) }

pan_input:                   # 流派特定排盘要素
  template: |                # markdown 模板(变量用 {key})
    # 八字排盘
    - 年柱：{fourPillars.year}
    - 月柱：{fourPillars.month}
    ...
  variables:                 # pan_input 用到的所有变量
    - { key: fourPillars.year,    type: string,  example: '壬午' }
    ...

style:                       # Style Requirements
  max_words: 500
  tone: warm
  banned_phrases: [...]      # 引用 compliance/mingli_banned_words.json 的关键词
  requirements:
    - 用概率性语言(通常/可能/倾向/建议)
    - 多具体场景(工作/感情/决策/家人)
    ...

output_format:               # 5 段输出契约
  - { id: total_lun,    title: '命格总论',  min_words: 80,  max_words: 120 }
  - { id: question,     title: '所问分析',  min_words: 100, max_words: 150 }
  - { id: season,       title: '时令建议',  min_words: 60,  max_words: 100 }
  - { id: quote,        title: '金句与寄语', min_words: 60,  max_words: 100 }
  - { id: term_bless,   title: '节气寄语',  min_words: 80,  max_words: 120 }

disclaimer:                  # 必填,引用 templates
  required: true
  template_ref: ../../specs/compliance/disclaimer_templates.json#/templates/schools/bazi
  fallback: '本解读基于传统命理算法生成,仅供文化体验与娱乐参考。'

tuning:                      # 调优参数
  temperature: 0.7
  max_tokens: 1500
  top_p: 0.9
  few_shot_count: 1          # 给几个示例
  rag: false                 # 是否需要 RAG 检索
  system_role_separate: true # Role 是否单独发 system prompt

notes: |                     # 流派特殊提示
  立春换年必须用 getYearInGanZhiByLiChun
```

## 后端使用方式

### Python(Flask 示例)

```python
import yaml, json
from jinja2 import Template

with open('specs/prompts/bazi.yaml') as f:
    spec = yaml.safe_load(f)

# 1. 加载输出 schema(强制 LLM 输出符合 schema)
with open(spec['output_schema_ref']) as f:
    output_schema = json.load(f)

# 2. 渲染 pan_input 模板
pan_template = Template(spec['pan_input']['template'])
pan_rendered = pan_template.render(
    gender=user_gender,
    question=user_question,
    fourPillars=four_pillars_dict,
    tst=tst_dict,
)

# 3. 组装最终 prompt
system_prompt = spec['role'] + '\n\n' + spec['style']['requirements_text']
user_prompt = spec['context_intro'] + '\n\n' + pan_rendered + '\n\n' + spec['output_format_intro']

# 4. 调 LLM,强制 JSON 输出
response = llm.chat(
    system=system_prompt,
    user=user_prompt,
    response_format={'type': 'json_schema', 'json_schema': output_schema},
)

# 5. 后处理:扫描禁词 + 截断超长段
validated = validate_response(response, spec)
```

### Node.js(给 v1.x 前端 demo 用,可选)

```js
const yaml = require('js-yaml');
const fs = require('fs');
const spec = yaml.load(fs.readFileSync('specs/prompts/bazi.yaml', 'utf8'));
// 类似地用模板引擎渲染
```

## 文件清单

| 文件 | 流派 | 状态 |
|---|---|---|
| `bazi.yaml` | 八字 | ✅ v1.0 |
| `ziwei.yaml` | 紫微 | ✅ v1.0 |
| `qimen.yaml` | 奇门 | ✅ v1.0 |
| `liuyao.yaml` | 六爻 | ✅ v1.0 |
| `meihua.yaml` | 梅花 | ✅ v1.0 |
| `tarot.yaml` | 塔罗 | ✅ v1.0 |
| `western-astro.yaml` | 西占 | ✅ v1.0 |
| `vedic.yaml` | 吠陀 | ✅ v1.0 |

## 校验

- `tests/liupai-reader-test.js` Layer 2.4 升级版可加:验证 8 个 YAML + 8 个 schema 的双向引用都自洽
- 提示:`output_schema_ref` 必须指向**已存在**的 `schools/*.result.schema.json`
- 提示:`disclaimer.template_ref` 必须指向 `compliance/disclaimer_templates.json` 已有的 key