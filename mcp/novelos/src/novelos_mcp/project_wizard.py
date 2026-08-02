from __future__ import annotations

from pathlib import Path
from typing import Any

from novelos_mcp.errors import NovelOSError


SECONDARY_DIRECTION_SUGGESTIONS = {
    "玄幻": ["东方玄幻", "高武世界", "宗门崛起", "无敌流", "升级流", "异世大陆", "王朝争霸", "神话复苏", "末法时代", "灵气枯竭", "黑暗纪元", "文明复兴", "守护苍生", "创世神话", "开天辟地", "诸神黄昏", "群像互助", "反英雄"],
    "奇幻": ["西方玄幻", "剑与魔法", "龙与地下城", "领主战争", "魔法学院", "蒸汽奇幻", "黑暗奇幻", "神明战争", "末日奇幻", "诸神黄昏", "失落纪元", "世界树", "造物主", "创世史诗", "文明复兴", "骑士守护", "反乌托邦", "灾厄降临"],
    "武侠": ["传统武侠", "新派武侠", "江湖恩怨", "门派纷争", "庙堂江湖", "悬疑武侠", "镖局江湖", "综武世界", "侠义复兴", "江湖末路", "乱世浮沉", "守护百姓", "武林浩劫", "门派中兴", "反英雄", "救世侠客", "旧秩序崩塌", "理想主义"],
    "仙侠": ["古典仙侠", "凡人流", "修真百艺", "洪荒神话", "门派经营", "家族修仙", "剑修", "诡道修仙", "末法时代", "灵气复苏", "天地大劫", "仙路断绝", "创世神话", "开天辟地", "诸神黄昏", "道统复兴", "守护人间", "逆天改命"],
    "都市": ["都市异能", "都市修仙", "商战职场", "娱乐明星", "神豪人生", "重生创业", "都市悬疑", "都市生活", "温暖治愈", "奋斗逆袭", "社区守护", "理想创业", "行业寒冬", "城市暗面", "秩序崩塌", "末日都市", "反乌托邦", "新城创世"],
    "现实": ["家庭伦理", "行业纪实", "成长青春", "社会派", "乡土现实", "医疗职场", "教育人生", "市井生活", "温暖治愈", "互助成长", "乡村振兴", "理想主义", "时代阵痛", "行业寒冬", "失序家庭", "社会阴影", "文明重建", "新生活实验"],
    "历史": ["架空历史", "秦汉三国", "两宋元明", "晚清民国", "战国权谋", "历史种田", "大航海", "宫廷权谋", "王朝中兴", "乱世救亡", "文明复兴", "理想变法", "王朝末世", "礼崩乐坏", "末法王朝", "开国创世", "新秩序建立", "史诗群像"],
    "军事": ["军旅生涯", "特种兵", "现代战争", "抗战谍战", "战术推演", "军工科技", "边境任务", "热血军旅", "和平守望", "灾后救援", "守护家园", "军民互助", "末日战场", "战争废墟", "失控武器", "文明保卫战", "新世界秩序", "悲壮牺牲"],
    "游戏": ["虚拟网游", "电竞职业", "游戏制作", "末日游戏", "全息网游", "卡牌对战", "领主游戏", "直播游戏", "治愈种田", "玩家共建", "文明复兴", "守护服务器", "死亡游戏", "反乌托邦副本", "世界崩坏", "创世沙盒", "造物主系统", "绝望求生"],
    "体育": ["竞技体育", "足球", "篮球", "网球", "田径", "运动成长", "教练生涯", "系统流体育", "团队复兴", "梦想赛场", "伤病治愈", "弱队逆袭", "职业低谷", "赛场黑幕", "时代落幕", "体育救赎", "新联赛创立", "热血群像"],
    "科幻": ["硬科幻", "星际文明", "机甲", "末世科幻", "时间循环", "人工智能", "宇宙探索", "科技争霸", "文明复兴", "星际救援", "理想星邦", "生态修复", "末法宇宙", "熵增末世", "黑暗森林", "反乌托邦", "创世工程", "人造神明"],
    "诸天无限": ["无限流", "诸天万界", "副本求生", "影视综漫", "主神空间", "时空穿梭", "任务流", "文明碰撞", "世界修复", "诸天守护", "文明火种", "理想联盟", "末法诸天", "世界毁灭", "绝望轮回", "神明陨落", "创世任务", "造物主试炼"],
    "悬疑": ["推理悬疑", "刑侦", "本格推理", "法医", "社会派", "惊悚", "诡秘悬疑", "密室逃脱", "救赎悬疑", "守护真相", "治愈推理", "城市微光", "末法诡异", "黑暗人性", "绝望求生", "世界崩坏", "创世谜团", "造物主阴影"],
    "轻小说": ["日常恋爱", "青春校园", "原生幻想", "异世界", "变身", "恋爱喜剧", "社团日常", "治愈日常", "伙伴羁绊", "校园救赎", "慢生活", "理想社团", "末日校园", "黑暗异世界", "绝望轮回", "世界终焉", "创世冒险", "新世界开拓"],
}


WIZARD_OPTIONS = {
    "channels": ["男频", "女频", "全向", "出版", "剧本"],
    "platforms": ["起点", "番茄", "晋江", "七猫"],
    "scales": ["短篇（1-100万字）", "中篇（100-300万字）", "长篇（300-500万字）", "超长篇（500万字以上）"],
    "primary_genres": ["玄幻", "奇幻", "武侠", "仙侠", "都市", "现实", "历史", "军事", "游戏", "体育", "科幻", "诸天无限", "悬疑", "轻小说"],
    "emotional_tones": ["爽快燃向", "轻松欢乐", "沙雕搞笑", "温馨治愈", "慢热沉浸", "热血悲壮", "黑暗压抑", "绝望求生", "冷峻克制", "疯癫混乱", "史诗厚重", "悬疑紧张"],
    "aesthetic_styles": ["东方古典", "魏晋风流", "盛唐气象", "蒸汽幻想", "西幻史诗", "黑暗哥特", "废土荒凉", "赛博霓虹", "星际宏伟", "民俗志怪", "宇宙恐怖", "校园青春", "市井烟火", "工业机械", "神秘学仪式"],
    "secondary_directions_by_primary_genre": SECONDARY_DIRECTION_SUGGESTIONS,
}


def project_wizard_html() -> str:
    return (Path(__file__).parent / "ui" / "project-wizard.html").read_text(encoding="utf-8")


def normalize_project_setup(payload: dict[str, Any]) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise NovelOSError("invalid_project_setup", "项目向导提交必须是对象")

    unexpected = sorted(set(payload) - {
        "title", "channel", "platform", "scale", "primary_genre", "secondary_directions",
        "emotional_tones", "aesthetic_styles", "reference_material", "creator",
    })
    if unexpected:
        raise NovelOSError("invalid_project_setup", "项目向导包含未支持字段", {"fields": unexpected})

    title = _text(payload.get("title"), "title")
    channel = _choice(payload.get("channel"), "channel", "channels")
    platform = _choice(payload.get("platform"), "platform", "platforms")
    scale = _choice(payload.get("scale"), "scale", "scales")
    primary_genre = _choice(payload.get("primary_genre"), "primary_genre", "primary_genres")
    secondary_directions = _text_list(payload.get("secondary_directions", []), "secondary_directions")
    unsupported_directions = sorted(set(secondary_directions) - set(SECONDARY_DIRECTION_SUGGESTIONS[primary_genre]))
    if unsupported_directions:
        raise NovelOSError(
            "invalid_project_setup",
            "二级方向必须来自当前一级题材的候选项",
            {"primary_genre": primary_genre, "values": unsupported_directions},
        )
    emotional_tones = _text_list(payload.get("emotional_tones", []), "emotional_tones")
    unsupported_tones = sorted(set(emotional_tones) - set(WIZARD_OPTIONS["emotional_tones"]))
    if unsupported_tones:
        raise NovelOSError("invalid_project_setup", "主情绪基调包含未支持选项", {"values": unsupported_tones})
    aesthetic_styles = _text_list(payload.get("aesthetic_styles", []), "aesthetic_styles")
    if len(aesthetic_styles) > 2:
        raise NovelOSError("invalid_project_setup", "美学风格最多选择两项")
    invalid_styles = sorted(set(aesthetic_styles) - set(WIZARD_OPTIONS["aesthetic_styles"]))
    if invalid_styles:
        raise NovelOSError("invalid_project_setup", "美学风格包含未支持选项", {"values": invalid_styles})

    reference_material = _optional_text(payload.get("reference_material"), "reference_material", max_length=10_000)
    creator = _creator_request(payload.get("creator"))

    creation_context = {
        "channel": channel,
        "platform": platform,
        "scale": scale,
        "primary_genre": primary_genre,
        "secondary_directions": secondary_directions,
        "reference_material": reference_material,
    }
    metadata = {
        "project_setup": {
            "version": 3,
            "creation_context": creation_context,
            "creator_selection": {"mode": creator["mode"]},
            "taxonomy": {
                "emotional_tones": emotional_tones,
                "aesthetic_styles": aesthetic_styles,
            },
        },
        "creation_status": "direction_pending",
    }
    description = f"{creation_context['channel']} · {primary_genre} · {scale}"
    return title, description, metadata, creator


def _creator_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NovelOSError("invalid_project_setup", "creator 必须是对象")
    mode = value.get("mode")
    if mode != "derive":
        raise NovelOSError(
            "invalid_project_setup",
            "项目向导仅支持原型派生 (mode='derive')",
            {"mode": mode},
        )
    expected = {"mode", "parent_version_id", "parent_subject_hash", "display_name", "overrides"}
    if set(value) != expected:
        raise NovelOSError(
            "invalid_project_setup",
            "creator 派生模式字段非法",
            {"mode": mode, "fields": sorted(value)},
        )
    normalized = dict(value)
    normalized["parent_version_id"] = _text(value["parent_version_id"], "parent_version_id")
    normalized["parent_subject_hash"] = _text(value["parent_subject_hash"], "parent_subject_hash")
    normalized["display_name"] = _text(value["display_name"], "display_name")
    if not isinstance(value["overrides"], dict) or not value["overrides"]:
        raise NovelOSError("invalid_project_setup", "creator.overrides 必须是非空对象")
    return normalized



def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NovelOSError("invalid_project_setup", f"{field} 必须是非空文本", {"field": field})
    return value.strip()


def _choice(value: Any, field: str, option_key: str) -> str:
    text = _text(value, field)
    if text not in WIZARD_OPTIONS[option_key]:
        raise NovelOSError("invalid_project_setup", f"{field} 包含未支持选项", {"field": field, "value": text})
    return text


def _text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise NovelOSError("invalid_project_setup", f"{field} 必须是字符串数组", {"field": field})
    return list(dict.fromkeys(item.strip() for item in value))


def _optional_text(value: Any, field: str, *, max_length: int) -> str | None:
    if value is None:
        return None
    text = _text(value, field)
    if len(text) > max_length:
        raise NovelOSError("invalid_project_setup", f"{field} 不能超过 {max_length} 个字符", {"field": field})
    return text
