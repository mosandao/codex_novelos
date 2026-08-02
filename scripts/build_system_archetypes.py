from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novelos_mcp.creative_contracts import CreativeContractStore
from novelos_mcp.hashing import content_hash

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "config" / "system_archetypes.json"

RAW_ARCHETYPES: list[dict[str, Any]] = [
    {
        "id": "system-epic-framework",
        "display_name": "体系史诗",
        "reader_promise": "规则、文明与人物命运彼此咬合",
        "genre_tags": ["玄幻", "奇幻", "仙侠", "科幻"],
        "temperament_tags": ["宏阔", "克制", "结构化"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在规则与时代缝隙中抗争并试图维护秩序的个体"],
            "distrusts": ["警惕缺乏约束的个体绝对武力与无代价力量膨胀"],
            "recurring_attention": ["持续关注力量体系演进、文明演变与规则背后的代价"],
            "narrative_principles": ["遵循力量必有代价与世界体系自我咬合的叙事逻辑"],
            "forbidden_conveniences": ["禁止无代价机械降神或凭空打破既定世界法则"],
            "expression_preferences": ["偏好宏阔克制、强调结构与因果交织的叙事笔触"],
            "negative_constraints": ["不得放弃力量体系的严密性与文明背景的厚重感"],
        },
    },
    {
        "id": "system-upward-striver",
        "display_name": "逆境攀登",
        "reader_promise": "低起点人物用选择和代价向上",
        "genre_tags": ["玄幻", "仙侠", "都市", "游戏", "体育"],
        "temperament_tags": ["坚韧", "热血", "递进"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理身处微贱却凭借意志与选择顽强向上突破的打拼者"],
            "distrusts": ["警惕不劳而获的虚妄幸运与靠血统特权凌驾他人的傲慢"],
            "recurring_attention": ["持续关注主角在资源匮乏与重重阶层压制下的生存策略"],
            "narrative_principles": ["保持明确的阶段性目标与脚踏实地的能力成长节奏"],
            "forbidden_conveniences": ["禁止无理由的越阶碾压或缺乏积累的凭空顿悟"],
            "expression_preferences": ["偏好紧凑递进、充满行动张力与爽快回馈的表达风格"],
            "negative_constraints": ["不得削弱逆境的真实压迫感与攀登过程的代价感"],
        },
    },
    {
        "id": "system-honor-in-action",
        "display_name": "侠义行动",
        "reader_promise": "行动中辨明责任、尊严与代价",
        "genre_tags": ["武侠", "军事", "历史", "玄幻"],
        "temperament_tags": ["果决", "悲壮", "正直"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在乱世或不公中敢于挺身而出、守护底线的行动者"],
            "distrusts": ["警惕以大局为名的冷酷牺牲与虚伪的高尚口号"],
            "recurring_attention": ["持续关注个体在道德抉择中的行动决策与尊严坚守"],
            "narrative_principles": ["强调行动优先、言出必行与承诺带来的不可逆后果"],
            "forbidden_conveniences": ["禁止事后妥协逃避责任或用巧合消解道德抉择的重压"],
            "expression_preferences": ["偏好干练果决、富有画面感与悲壮宿命感的叙事节奏"],
            "negative_constraints": ["不得将侠义降格为无脑莽撞或虚无主义的无差别暴力"],
        },
    },
    {
        "id": "system-community-builder",
        "display_name": "群像共建",
        "reader_promise": "分歧中的人走向协作与共同体",
        "genre_tags": ["现实", "都市", "历史", "军事", "游戏"],
        "temperament_tags": ["温厚", "务实", "群像"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理背景迥异却在共同事业中相互补完的普通建设者"],
            "distrusts": ["警惕独夫专断、抹杀个体差异的集权思想与内耗投机"],
            "recurring_attention": ["持续关注不同角色的利益诉求、分歧调和与协作机制"],
            "narrative_principles": ["遵循群像互补、多视角交织与共同体逐步建立的规律"],
            "forbidden_conveniences": ["禁止降智工具人或强行用个人光环掩盖团队合作价值"],
            "expression_preferences": ["偏好温厚务实、注重细节刻画与人情世故的多元视角表达"],
            "negative_constraints": ["不得抹杀配角的主体性或将共同体建设简单化为一人独舞"],
        },
    },
    {
        "id": "system-rational-inference",
        "display_name": "理性推演",
        "reader_promise": "清晰约束下的意外且必然",
        "genre_tags": ["科幻", "历史", "游戏", "现实"],
        "temperament_tags": ["冷静", "严谨", "逻辑"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理恪守理性法则、在有限信息中寻找最优解的探求者"],
            "distrusts": ["警惕基于情绪化的盲目豪赌与缺乏事实依据的神秘主义"],
            "recurring_attention": ["持续关注前提条件设定、因果推演逻辑与推断可回溯性"],
            "narrative_principles": ["遵循信息完备、逻辑自洽与情理之中意料之外的解谜原则"],
            "forbidden_conveniences": ["禁止临时篡改既有规则或依赖无法推演的降维打法"],
            "expression_preferences": ["偏好冷静严谨、条理清晰且富于智力愉悦感的叙事语言"],
            "negative_constraints": ["不得出现逻辑漏洞、双标推论或凭空捏造未知前提"],
        },
    },
    {
        "id": "system-disaster-survivor",
        "display_name": "灾厄求生",
        "reader_promise": "极端压力下守住人性与判断",
        "genre_tags": ["科幻", "奇幻", "悬疑", "诸天无限"],
        "temperament_tags": ["高压", "坚忍", "危机"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在灾难与绝境中顽强求生并守住理智底线的幸存者"],
            "distrusts": ["警惕危机中的盲目恐慌、道德绑架与毫无人性的极端利己"],
            "recurring_attention": ["持续关注资源枯竭限制、危机环境压迫与求生抉择代价"],
            "narrative_principles": ["保持高压危机感、严苛的资源消耗规则与不可逆的环境变化"],
            "forbidden_conveniences": ["禁止无尽物资供给或在致命危机中强行安排安全庇护"],
            "expression_preferences": ["偏好紧张扣人心弦、侧重生动感官体验与高压心理的描写"],
            "negative_constraints": ["不得削弱生存危机的真实威胁或消解绝境中的人道底线"],
        },
    },
    {
        "id": "system-fair-truth",
        "display_name": "公平求真",
        "reader_promise": "真相来自可回溯线索与动机",
        "genre_tags": ["悬疑", "都市", "历史", "现实"],
        "temperament_tags": ["克制", "精确", "悬念"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理不畏迷雾与压力、坚持追寻客观事实真相的追查者"],
            "distrusts": ["警惕主观先入为主的偏见、权力掩盖真相与伪造证据"],
            "recurring_attention": ["持续关注线索链条完整性、动机合理性与证据闭环过程"],
            "narrative_principles": ["遵循公平悬疑原则，所有关键线索必须对读者公开回溯"],
            "forbidden_conveniences": ["禁止临近结尾隐瞒核心线索或用超自然理由解释犯罪"],
            "expression_preferences": ["偏好克制精确、注重线索铺垫与推理反转的悬念表达"],
            "negative_constraints": ["不得破坏线索与真相的公平对等关系或依赖天降巧合破案"],
        },
    },
    {
        "id": "system-folklore-echo",
        "display_name": "民俗幽微",
        "reader_promise": "异常与日常交织，恐惧背后有人情",
        "genre_tags": ["悬疑", "奇幻", "仙侠", "武侠"],
        "temperament_tags": ["诗性", "诡谲", "悲悯"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理被困于奇异规约、古老习俗或悲剧宿命中的幽微众生"],
            "distrusts": ["警惕粗暴破坏民俗秩序的狂妄武断与缺乏悲悯的猎奇心态"],
            "recurring_attention": ["持续关注民间志怪传说、地方规约与古老恐惧背后的执念"],
            "narrative_principles": ["遵循日常与奇诡交织、异象映射人心欲望与情感的原则"],
            "forbidden_conveniences": ["禁止用纯物理暴力粗暴抹杀具有文化内涵的奇异现象"],
            "expression_preferences": ["偏好具诗性氛围、诡谲幽深且富有中式悲悯色彩的文风"],
            "negative_constraints": ["不得沦为毫无人文情怀的廉价吓人或脱离地方风土的空洞怪谈"],
        },
    },
    {
        "id": "system-institutional-lens",
        "display_name": "制度观察",
        "reader_promise": "个体命运在资源与时代中变化",
        "genre_tags": ["历史", "现实", "都市", "军事"],
        "temperament_tags": ["厚重", "清醒", "多视角"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在体制、结构与时代浪潮中挣扎浮沉并试图破局的思考者"],
            "distrusts": ["警惕将复杂社会历史问题简单化归咎于个别恶人的幼稚观"],
            "recurring_attention": ["持续关注资源分配博弈、权力运行机制与结构性困境演变"],
            "narrative_principles": ["遵循制度决定利益、利益驱动行为与时代重塑个体命运的逻辑"],
            "forbidden_conveniences": ["禁止靠主角个人口号瞬间改变千年积累的利益结构"],
            "expression_preferences": ["偏好厚重清醒、多视角穿透与深刻洞察社会机理的笔法"],
            "negative_constraints": ["不得忽视制度与环境对人物行为的深层塑造力"],
        },
    },
    {
        "id": "system-everyday-repair",
        "display_name": "市井治愈",
        "reader_promise": "平凡关系里的修复、成长与互助",
        "genre_tags": ["都市", "现实", "轻小说"],
        "temperament_tags": ["温暖", "细腻", "生活流"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在日常生活中承受微小创伤却依然善待他人的平凡人"],
            "distrusts": ["警惕虚无冷漠的社会疏离感与刻意制造无意义痛苦的恶趣"],
            "recurring_attention": ["持续关注生活细琐温情、美食手艺与人与人之间的微小修复"],
            "narrative_principles": ["遵循生活流叙事、通过微观互动展现心理疗愈与关系成长"],
            "forbidden_conveniences": ["禁止突然插入恶俗狗血冲突或破坏温馨生活基调的恶性事件"],
            "expression_preferences": ["偏好温暖细腻、富有生活气息与治愈人心的轻松语调"],
            "negative_constraints": ["不得滑向浮夸虚假的工业糖精或空洞无物的水字数日常"],
        },
    },
    {
        "id": "system-youthful-bonds",
        "display_name": "青春与情感羁绊",
        "reader_promise": "年轻人在关系、情感拉扯、梦想与自我中长成",
        "genre_tags": ["轻小说", "都市", "现实", "体育"],
        "temperament_tags": ["明亮/强张力", "真诚", "宿命"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在青春迷茫、情感博弈与宿命羁绊中勇敢追寻自我的年轻心灵"],
            "distrusts": ["警惕功利算计亲密关系、玩弄情感与对真诚承诺的轻蔑"],
            "recurring_attention": ["持续关注人物间的情感张力、关系拉扯、双向救赎与自我确认"],
            "narrative_principles": ["遵循情感博弈自洽、关系演进有据与梦想与羁绊双向提振"],
            "forbidden_conveniences": ["禁止无缘由的降智误会或缺乏情感积淀的硬凑亲密"],
            "expression_preferences": ["偏好情感充沛、富于心理拉扯张力与明亮真诚的表达笔致"],
            "negative_constraints": ["不得剥离情感博弈中的真诚性或将青春关系降格为低俗套路"],
        },
    },
    {
        "id": "system-contrast-adventure",
        "display_name": "反差与荒诞解构",
        "reader_promise": "严肃目标与轻快日常/荒诞吐槽彼此提振",
        "genre_tags": ["游戏", "轻小说", "都市", "诸天无限"],
        "temperament_tags": ["幽默", "解构", "对话驱动"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在沉重世界观下依然保持乐观吐槽、用反差与荒诞解构严肃的旅人"],
            "distrusts": ["警惕死板教条的陈词滥调与缺乏幽默感、自以为是的说教"],
            "recurring_attention": ["持续关注严肃设定的反差呈现、吐槽解构与轻快喜剧效果"],
            "narrative_principles": ["遵循反差解构有度、对话诙谐风趣与主线目标不失衡的原则"],
            "forbidden_conveniences": ["禁止无底线的滥用恶搞导致世界观彻底崩塌或主线丧失吸引力"],
            "expression_preferences": ["偏好对话驱动、节奏明快、充满机智吐槽与反差萌点的语言"],
            "negative_constraints": ["不得因荒诞解构而消解核心目标的严肃性或沦为低俗烂梗堆砌"],
        },
    },
    {
        "id": "system-shadowed-choice",
        "display_name": "暗影与暗黑博弈",
        "reader_promise": "没有完美选项，主角以利己/灰色选择承担后果与黑洞",
        "genre_tags": ["奇幻", "玄幻", "悬疑", "诸天无限"],
        "temperament_tags": ["冷峻", "暗黑", "复杂", "反英雄/恶人"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在残酷黑洞秩序中以利己算计、暗黑手段生存并承担道德后果的行者"],
            "distrusts": ["警惕虚伪的道德圣母口号与毫无准备的盲目善意给自身带来的毁灭"],
            "recurring_attention": ["持续关注灰色抉择代价、暗黑人性博弈与利益最大化算计"],
            "narrative_principles": ["遵循暗黑生存法则、冷酷代价计算与反英雄/恶人选择的不可逆后果"],
            "forbidden_conveniences": ["禁止天降正义道德救赎或靠天真善意无伤化解黑暗博弈"],
            "expression_preferences": ["偏好冷峻硬朗、直面人性暗面与充满生存博弈张力的笔法"],
            "negative_constraints": ["不得用正派道德框架阉割主角的利己算计或掩盖暗黑博弈的残酷性"],
        },
    },
    {
        "id": "system-restoration-craft",
        "display_name": "经营复兴",
        "reader_promise": "用资源、技艺和关系重建衰败之地",
        "genre_tags": ["历史", "都市", "仙侠", "游戏"],
        "temperament_tags": ["耐心", "建设", "成就"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理依靠专业技艺、资源整合与耐心经营让衰败事物重焕生机的建设者"],
            "distrusts": ["警惕掠夺破产式投机与破坏生产力成果的掠夺行为"],
            "recurring_attention": ["持续关注产业资源流转、技术细节突破与积累式建设成就感"],
            "narrative_principles": ["遵循积累递进、技艺出真知与经营复兴符合经济逻辑的规律"],
            "forbidden_conveniences": ["禁止凭空变出无限资源或无视生产规律的瞬间神迹"],
            "expression_preferences": ["偏好耐心扎实、富于专业细节与获得感满满的表达方式"],
            "negative_constraints": ["不得脱离物理与经济建设规律或将复兴过程敷衍化处理"],
        },
    },
    {
        "id": "system-tactical-teamwork",
        "display_name": "战术协作",
        "reader_promise": "胜利来自信息、配合和临场判断",
        "genre_tags": ["军事", "体育", "游戏", "科幻"],
        "temperament_tags": ["紧张", "专业", "团队"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在战术博弈中高度信任队友、依靠信息与执行力克敌的专业团队"],
            "distrusts": ["警惕脱离团队配合的个人英雄主义与违背战术常识的蛮干"],
            "recurring_attention": ["持续关注战场/赛场信息差、团队分工配合与临场决策修正"],
            "narrative_principles": ["遵循战术自洽、专业配合胜于单打独斗与信息即胜负的原则"],
            "forbidden_conveniences": ["禁止忽视战术阵型与指挥系统而靠个人爆种无伤翻盘"],
            "expression_preferences": ["偏好节奏紧密、专业术语准确且充满团队热血感的叙事节奏"],
            "negative_constraints": ["不得违背战术推演逻辑或将团队成员降级为背景板"],
        },
    },
    {
        "id": "system-civilization-voyage",
        "display_name": "文明远航",
        "reader_promise": "探索未知并追问文明如何延续",
        "genre_tags": ["科幻", "奇幻", "诸天无限"],
        "temperament_tags": ["好奇", "壮阔", "探索"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理怀抱好奇心与敬畏感、踏入未知星空/秘境探索文明未来的远航者"],
            "distrusts": ["警惕傲慢的文明征服欲与因无知恐惧而产生的毁灭性排他心理"],
            "recurring_attention": ["持续关注异质文明形态、宏大宇宙景观与文明延续的哲学思考"],
            "narrative_principles": ["遵循探索未知的壮阔好奇感、文明碰撞逻辑与敬畏自然的原则"],
            "forbidden_conveniences": ["禁止将未知文明浅薄化为低级怪兽或凭空忽视宏大空间尺度"],
            "expression_preferences": ["偏好壮阔好奇、富于诗意想象与宇宙史诗感的大气笔触"],
            "negative_constraints": ["不得削弱宇宙与未知的宏伟尺度或将文明远航降格为狭隘争斗"],
        },
    },
    {
        "id": "system-psychological-maze",
        "display_name": "心理迷宫与人性博弈",
        "reader_promise": "外部谜题与智斗映照创伤、欲望、算计与人性黑洞",
        "genre_tags": ["悬疑", "现实", "都市", "轻小说"],
        "temperament_tags": ["内省", "压抑", "智斗", "细密"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在人性黑洞、心理防线博弈与自我创伤中苦苦智斗的探寻者"],
            "distrusts": ["警惕虚饰的人性假象、心理操纵与自我欺骗带来的毁灭风险"],
            "recurring_attention": ["持续关注人心隐秘欲望、算计试探、心理死局与人性博弈细节"],
            "narrative_principles": ["遵循心理自洽、智斗防线拉扯与外部谜题映射内心深渊的原则"],
            "forbidden_conveniences": ["禁止粗暴的口号式心理救赎或忽视心理防线突兀反转"],
            "expression_preferences": ["偏好细密内省、充满心理悬念张力与人性幽微剖析的笔感"],
            "negative_constraints": ["不得浅薄化人性复杂博弈或用粗暴解法消解心理死局的深度"],
        },
    },
    {
        "id": "system-fate-cultivation",
        "display_name": "宿命修行",
        "reader_promise": "以修行、承诺和选择改变既定秩序",
        "genre_tags": ["仙侠", "玄幻", "武侠", "奇幻"],
        "temperament_tags": ["古典", "沉潜", "执着"],
        "signature": {
            "schema_version": 1,
            "sympathies": ["同理在天道宿命压制下沉潜修心、以执念与承诺向死而生的修行者"],
            "distrusts": ["警惕顺从宿命天道的虚无主义与背弃初心承诺的投机求存"],
            "recurring_attention": ["持续关注道心磨砺、宿命枷锁对抗与古朴承诺的兑现代价"],
            "narrative_principles": ["遵循修心即修道、选择重于天赋与承诺重于生死的古典韵味"],
            "forbidden_conveniences": ["禁止脱离心性修持的投机突破或无代价改变既定天命"],
            "expression_preferences": ["偏好古典沉潜、含蓄隽永且富于哲理意味的文言韵味表达"],
            "negative_constraints": ["不得剥离修行的道心修持本质或将宿命对抗浅薄化为快餐升级"],
        },
    },
]


def main() -> None:
    store = CreativeContractStore()
    archetypes: list[dict[str, Any]] = []

    for item in RAW_ARCHETYPES:
        validated_sig = store.validate_signature(item["signature"])
        hash_val = content_hash(json.dumps(validated_sig, sort_keys=True, ensure_ascii=False))
        entry = {
            "id": item["id"],
            "display_name": item["display_name"],
            "ownership": "system_archetype",
            "reader_promise": item["reader_promise"],
            "genre_tags": item["genre_tags"],
            "temperament_tags": item["temperament_tags"],
            "revision": 1,
            "subject_hash": hash_val,
            "signature": validated_sig,
        }
        archetypes.append(entry)

    OUTPUT_PATH.write_text(json.dumps(archetypes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Successfully generated {len(archetypes)} system archetypes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
