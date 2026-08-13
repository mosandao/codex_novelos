from __future__ import annotations

from typing import Any

GENRE_TEMPERAMENT_MAP: dict[str, list[str]] = {
    "玄幻": ["宏阔", "克制", "坚韧", "递进", "暗黑"],
    "奇幻": ["宏阔", "克制", "高压", "好奇", "暗黑"],
    "武侠": ["果决", "悲壮", "正直", "古典"],
    "仙侠": ["古典", "沉潜", "执着", "坚韧"],
    "都市": ["温厚", "务实", "温暖", "细腻", "真诚"],
    "现实": ["厚重", "清醒", "温厚", "多视角"],
    "历史": ["厚重", "清醒", "耐心", "建设"],
    "军事": ["紧张", "专业", "团队", "果决"],
    "游戏": ["幽默", "解构", "紧张", "团队"],
    "体育": ["紧张", "专业", "热血", "递进"],
    "科幻": ["冷静", "严谨", "逻辑", "好奇", "壮阔"],
    "诸天无限": ["高压", "坚忍", "好奇", "解构", "暗黑"],
    "悬疑": ["克制", "精确", "悬念", "内省", "智斗"],
    "轻小说": ["明亮/强张力", "幽默", "解构", "温暖", "真诚"],
}

TONE_TEMPERAMENT_MAP: dict[str, list[str]] = {
    "爽快燃向": ["热血", "递进", "坚韧"],
    "轻松欢乐": ["幽默", "解构", "对话驱动"],
    "沙雕搞笑": ["幽默", "解构", "对话驱动"],
    "温馨治愈": ["温暖", "细腻", "生活流"],
    "慢热沉浸": ["沉潜", "古典", "厚重"],
    "热血悲壮": ["悲壮", "正直", "果决"],
    "黑暗压抑": ["暗黑", "反英雄/恶人", "高压", "冷峻"],
    "绝望求生": ["高压", "坚忍", "危机"],
    "冷峻克制": ["冷峻", "克制", "冷静"],
    "疯癫混乱": ["复杂", "暗黑", "反英雄/恶人"],
    "史诗厚重": ["宏阔", "结构化", "厚重"],
    "悬疑紧张": ["悬念", "精确", "智斗", "内省"],
}


def recommend_archetypes(
    primary_genre: str,
    secondary_directions: list[str],
    emotional_tones: list[str],
    aesthetic_styles: list[str],
    archetypes: list[dict[str, Any]],
) -> list[str]:
    """
    确定性打分算法，为项目定位推荐 Top 3 系统叙事原型。
    """
    scores: list[tuple[float, int, str]] = []

    for idx, archetype in enumerate(archetypes):
        score = 0.0
        g_tags: list[str] = archetype.get("genre_tags", [])
        t_tags: list[str] = archetype.get("temperament_tags", [])
        promise: str = archetype.get("reader_promise", "")

        # 1. 一级题材匹配 (10分)
        if primary_genre in g_tags:
            score += 10.0

        # 2. 情绪基调匹配 (每匹配一项 +3分)
        for tone in emotional_tones:
            expected_temps = TONE_TEMPERAMENT_MAP.get(tone, [])
            for t in t_tags:
                if t in expected_temps or any(et in t for et in expected_temps):
                    score += 3.0

        # 3. 题材期望气质加分 (+2分)
        expected_genre_temps = GENRE_TEMPERAMENT_MAP.get(primary_genre, [])
        for t in t_tags:
            if any(egt in t for egt in expected_genre_temps):
                score += 2.0

        # 4. 二级方向/美学风格与读者承诺文本重合加分
        for sec in secondary_directions:
            if sec in promise or any(tag in sec for tag in g_tags + t_tags):
                score += 1.5

        for aes in aesthetic_styles:
            if aes in promise or any(tag in aes for tag in t_tags):
                score += 1.0

        # idx 作为次要排序规则，保证相同分数下顺序确定
        scores.append((score, -idx, archetype["id"]))

    # 按分数降序排列
    scores.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item[2] for item in scores[:3]]


def generate_derivation_draft(
    archetype: dict[str, Any],
    project_setup: dict[str, Any],
) -> dict[str, list[str]]:
    """
    确定性纯函数：基于选定的系统原型与项目 Setup，草拟仅包含项目化显式差异的草稿。
    只允许草拟: recurring_attention, narrative_principles, expression_preferences, forbidden_conveniences.
    绝对不覆盖 sympathies, distrusts, negative_constraints 等只读底色。
    """
    creation_ctx = project_setup.get("creation_context", {})
    taxonomy = project_setup.get("taxonomy", {})
    primary_genre = creation_ctx.get("primary_genre", "")
    secondary_directions = creation_ctx.get("secondary_directions", [])
    emotional_tones = taxonomy.get("emotional_tones", [])
    aesthetic_styles = taxonomy.get("aesthetic_styles", [])

    base_signature = archetype.get("signature", {})
    overrides: dict[str, list[str]] = {}

    # 1. recurring_attention (项目专注点)
    rec_att = list(base_signature.get("recurring_attention", []))
    suffix_items: list[str] = []
    if secondary_directions:
        sec_str = "、".join(secondary_directions[:2])
        suffix_items.append(f"重点聚焦在《{sec_str}》方向下的核心矛盾与情节推进")
    if aesthetic_styles:
        aes_str = "、".join(aesthetic_styles[:2])
        suffix_items.append(f"融入【{aes_str}】风格氛围的具象细节描写")
    if suffix_items:
        new_rec = rec_att + [item for item in suffix_items if item not in rec_att]
        if new_rec != rec_att:
            overrides["recurring_attention"] = new_rec

    # 2. narrative_principles (叙事原则)
    narr_prin = list(base_signature.get("narrative_principles", []))
    if emotional_tones:
        tone_str = "、".join(emotional_tones[:2])
        new_principle = f"保持【{tone_str}】的情感基调与叙事张力"
        if new_principle not in narr_prin:
            overrides["narrative_principles"] = narr_prin + [new_principle]

    # 3. expression_preferences (表达偏好)
    exp_pref = list(base_signature.get("expression_preferences", []))
    if primary_genre or aesthetic_styles:
        pref_str = f"契合{primary_genre}频道的读者阅读习惯"
        if aesthetic_styles:
            pref_str += f"，强化【{aesthetic_styles[0]}】画面感"
        if pref_str not in exp_pref:
            overrides["expression_preferences"] = exp_pref + [pref_str]

    return overrides
