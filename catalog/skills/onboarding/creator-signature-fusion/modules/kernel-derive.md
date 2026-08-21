## 内核派生分支（v3）：从根长分身

payload 携带 `setup.author_kernel`（select 形态，缝合或直选）时走本分支——`kernel_full` 是分身的第一因：

- **parent 即内核版本**：`parent_version_id` = author_kernel.kernel_version_id，`parent_subject_hash` = 内核 subject_hash（以注入的 kernel_full 节首行 hash 为准）。系统原型全库此时只是参考资料——禁止从原型取 parent。
- **内核层继承不变**：分身的核心问题感、价值排序、心理运作（八维）、知识边界必须能追溯到内核的 identity / psychology / knowledge_ecology——语义继承、重新长出，**禁止逐字复制内核条目**（校验门逐条比对 core_questions / value_axioms / aesthetic_commitments / creative_axioms）。
- **表达层按本书适配**：narrative 的生平五维、trait_profile、voice_samples、七字段规约按 setup 的频道/题材/平台/表里基调校准——同一个内核在仙侠与言情长出的分身，深层判断一致，口吻与手法不同。adaptation_notes（kernel_origin 内）写清本次适配了什么。
- **wound→fear 链在分身层照常执行**：内核不预设创伤来源；分身立人时按 1.4 的恐惧纪律给 refuses 追溯可心理化的来源（内核层素材优先）。
- **盲区双重来源**：cannot_write 除库存空白外，纳入内核 kernel_blindspots.overlooks 的分身化转写（ overlooks 说「容易忽略身体细节」，分身就声明「写不了纯身体对抗——绕开：借旁观者视角写结果」）。
- `signature.kernel_origin` 必填：kernel_version_id + kernel_subject_hash + adaptation_notes（适配说明）。

## 附加自检

- kernel_origin 三字段齐全且与注入的内核 hash 一致。
- 七字段逐条自查：无逐字复制内核 identity 条目；深层判断可溯源。
- adaptation_notes 说明了频道/题材/平台的具体适配点（不是空话）。
