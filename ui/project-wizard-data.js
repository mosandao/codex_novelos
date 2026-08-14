// NovelOS 新建项目向导 · 静态权威数据。
// 频道×平台/题材/二级方向/基调池/美学推荐/题材信息包/推荐规则在此维护（唯一来源）。
// system_archetypes 镜像自 config/system_archetypes.json（含 channel_affinity 元数据）；修改原型请改 config 后同步此镜像。
window.NOVELOS_WIZARD_DATA = {
  "channels": {
    "男频": {
      "platforms": [
        "起点",
        "番茄",
        "七猫",
        "纵横"
      ]
    },
    "女频": {
      "platforms": [
        "晋江",
        "番茄",
        "七猫"
      ]
    },
    "全向": {
      "platforms": [
        "番茄",
        "七猫"
      ]
    }
  },
  "platform_traits": {
    "起点": {
      "model": "付费订阅",
      "patience": "养书容忍，前期可慢热铺体系",
      "reader_profile": "男频付费核心读者，体系流/设定流传统深厚，接受中长线铺垫"
    },
    "番茄": {
      "model": "免费算法",
      "patience": "开篇即冲突、高密度兑现，前三章定生死",
      "reader_profile": "下沉市场海量读者，30-49 岁为主力，节奏碎片化、要快节奏强钩子"
    },
    "七猫": {
      "model": "免费算法",
      "patience": "开篇即冲突、高密度兑现",
      "reader_profile": "免费阅读大盘读者，偏熟龄，题材宽容度高、要求直给"
    },
    "晋江": {
      "model": "社区付费",
      "patience": "养书容忍，情感线密度与基调敏感",
      "reader_profile": "女频高粘性社区读者，重人物关系与情感逻辑，对烂梗与降智敏感"
    },
    "纵横": {
      "model": "付费订阅",
      "patience": "养书容忍",
      "reader_profile": "男频付费读者，传统玄幻/军事/历史基本盘"
    }
  },
  "genres": {
    "男频": [
      "玄幻",
      "奇幻",
      "武侠",
      "仙侠",
      "都市",
      "现实",
      "历史",
      "军事",
      "游戏",
      "体育",
      "科幻",
      "诸天无限",
      "悬疑",
      "轻小说"
    ],
    "女频": [
      "古代言情",
      "现代言情",
      "幻想言情",
      "仙侠奇缘",
      "玄幻言情",
      "浪漫青春",
      "悬疑灵异",
      "游戏竞技"
    ],
    "全向": [
      "都市",
      "现实",
      "历史",
      "悬疑",
      "游戏",
      "体育",
      "科幻",
      "轻小说"
    ]
  },
  "secondary_directions": {
    "男频": {
      "玄幻": [
        "东方玄幻",
        "异世大陆",
        "高武世界",
        "王朝争霸",
        "现代魔法",
        "神话复苏",
        "无敌流",
        "升级流",
        "宗门经营",
        "黑暗流"
      ],
      "奇幻": [
        "西方奇幻",
        "剑与魔法",
        "领主战争",
        "魔法学院",
        "史诗奇幻",
        "黑暗奇幻",
        "蒸汽奇幻",
        "神明战争"
      ],
      "武侠": [
        "传统武侠",
        "新派武侠",
        "江湖恩怨",
        "门派纷争",
        "庙堂江湖",
        "悬疑武侠",
        "镖局江湖",
        "综武世界"
      ],
      "仙侠": [
        "古典仙侠",
        "凡人流",
        "修真百艺",
        "洪荒神话",
        "门派经营",
        "家族修仙",
        "剑修",
        "诡道修仙",
        "末法时代",
        "灵气复苏",
        "仙路断绝"
      ],
      "都市": [
        "都市异能",
        "都市修仙",
        "商战职场",
        "娱乐明星",
        "神豪人生",
        "重生创业",
        "都市悬疑",
        "都市生活",
        "行业文"
      ],
      "现实": [
        "家庭伦理",
        "行业纪实",
        "社会派",
        "乡土现实",
        "医疗职场",
        "教育人生",
        "市井生活",
        "年代文"
      ],
      "历史": [
        "架空历史",
        "秦汉三国",
        "两宋元明",
        "晚清民国",
        "战国权谋",
        "历史种田",
        "大航海",
        "权谋宫廷"
      ],
      "军事": [
        "军旅生涯",
        "特种兵",
        "现代战争",
        "抗战谍战",
        "战术推演",
        "军工科技",
        "边境任务",
        "末日战场"
      ],
      "游戏": [
        "虚拟网游",
        "电竞职业",
        "游戏制作",
        "末日游戏",
        "全息网游",
        "卡牌对战",
        "领主游戏",
        "死亡游戏"
      ],
      "体育": [
        "竞技体育",
        "足球",
        "篮球",
        "网球",
        "田径",
        "教练生涯",
        "系统流体育",
        "弱队逆袭"
      ],
      "科幻": [
        "硬科幻",
        "星际文明",
        "机甲",
        "末世科幻",
        "时间循环",
        "人工智能",
        "宇宙探索",
        "黑暗森林"
      ],
      "诸天无限": [
        "无限流",
        "诸天万界",
        "副本求生",
        "影视综漫",
        "主神空间",
        "时空穿梭",
        "任务流",
        "世界修复"
      ],
      "悬疑": [
        "推理悬疑",
        "刑侦",
        "本格推理",
        "法医",
        "社会派",
        "惊悚",
        "诡秘悬疑",
        "密室逃脱",
        "民俗怪谈"
      ],
      "轻小说": [
        "日常恋爱",
        "青春校园",
        "原生幻想",
        "异世界",
        "变身",
        "恋爱喜剧",
        "社团日常",
        "异能日常"
      ]
    },
    "女频": {
      "古代言情": [
        "宅斗",
        "宫斗",
        "种田经商",
        "穿越重生",
        "女强权谋",
        "和离再嫁",
        "古代探案",
        "闺门日常",
        "嫡女归来",
        "婆媳妯娌"
      ],
      "现代言情": [
        "都市婚恋",
        "职场成长",
        "年代文",
        "豪门恩怨",
        "萌宝团宠",
        "马甲大佬",
        "真假千金",
        "追妻火葬场",
        "破镜重圆",
        "先婚后爱"
      ],
      "幻想言情": [
        "快穿任务",
        "穿书自救",
        "无限流",
        "规则怪谈",
        "星际言情",
        "西幻言情",
        "异能觉醒",
        "直播玄学"
      ],
      "仙侠奇缘": [
        "修仙言情",
        "仙门种田",
        "灵宠经营",
        "飞升日常",
        "反派自救",
        "修真家族",
        "仙界经营",
        "双强仙途"
      ],
      "玄幻言情": [
        "女强升级",
        "异世大陆",
        "兽世",
        "女尊",
        "神魔之恋",
        "废柴逆袭",
        "魂穿异世",
        "御兽"
      ],
      "浪漫青春": [
        "校园初恋",
        "竞技青春",
        "娱乐圈",
        "双向暗恋",
        "学园异能",
        "青春疼痛",
        "顶流恋爱"
      ],
      "悬疑灵异": [
        "规则怪谈",
        "民俗诡事",
        "女探推理",
        "惊悚副本",
        "玄学直播",
        "灵异摆渡",
        "无限闯关"
      ],
      "游戏竞技": [
        "电竞恋爱",
        "全息网游",
        "网游情缘",
        "游戏制作",
        "直播游戏",
        "竞技甜宠",
        "战队日常"
      ]
    },
    "全向": {
      "都市": [
        "都市异能",
        "都市生活",
        "商战职场",
        "都市悬疑",
        "行业文",
        "重生创业"
      ],
      "现实": [
        "家庭伦理",
        "行业纪实",
        "社会派",
        "乡土现实",
        "医疗职场",
        "年代文"
      ],
      "历史": [
        "架空历史",
        "秦汉三国",
        "两宋元明",
        "晚清民国",
        "历史种田",
        "权谋宫廷"
      ],
      "悬疑": [
        "推理悬疑",
        "刑侦",
        "本格推理",
        "法医",
        "惊悚",
        "民俗怪谈"
      ],
      "游戏": [
        "虚拟网游",
        "电竞职业",
        "游戏制作",
        "全息网游",
        "死亡游戏"
      ],
      "体育": [
        "竞技体育",
        "足球",
        "篮球",
        "教练生涯",
        "弱队逆袭"
      ],
      "科幻": [
        "硬科幻",
        "星际文明",
        "机甲",
        "末世科幻",
        "时间循环",
        "人工智能"
      ],
      "轻小说": [
        "日常恋爱",
        "青春校园",
        "异世界",
        "恋爱喜剧",
        "社团日常"
      ]
    }
  },
  "tone_pools": {
    "男频": [
      {
        "value": "爽快燃向",
        "pole": "neutral"
      },
      {
        "value": "轻松欢乐",
        "pole": "light"
      },
      {
        "value": "沙雕搞笑",
        "pole": "light"
      },
      {
        "value": "温馨治愈",
        "pole": "light"
      },
      {
        "value": "慢热沉浸",
        "pole": "neutral"
      },
      {
        "value": "热血悲壮",
        "pole": "neutral"
      },
      {
        "value": "黑暗压抑",
        "pole": "dark"
      },
      {
        "value": "绝望求生",
        "pole": "dark"
      },
      {
        "value": "冷峻克制",
        "pole": "neutral"
      },
      {
        "value": "疯癫混乱",
        "pole": "dark"
      },
      {
        "value": "史诗厚重",
        "pole": "neutral"
      },
      {
        "value": "悬疑紧张",
        "pole": "neutral"
      }
    ],
    "女频": [
      {
        "value": "甜宠治愈",
        "pole": "light"
      },
      {
        "value": "轻松搞笑",
        "pole": "light"
      },
      {
        "value": "爽文逆袭",
        "pole": "neutral"
      },
      {
        "value": "复仇打脸",
        "pole": "neutral"
      },
      {
        "value": "虐恋情深",
        "pole": "dark"
      },
      {
        "value": "破镜重圆",
        "pole": "neutral"
      },
      {
        "value": "事业成长",
        "pole": "neutral"
      },
      {
        "value": "悬疑烧脑",
        "pole": "neutral"
      },
      {
        "value": "黑暗压抑",
        "pole": "dark"
      },
      {
        "value": "家国豪情",
        "pole": "neutral"
      },
      {
        "value": "慢热沉浸",
        "pole": "neutral"
      },
      {
        "value": "疯批张力",
        "pole": "dark"
      }
    ]
  },
  "aesthetic_styles": [
    "东方古典",
    "魏晋风流",
    "盛唐气象",
    "蒸汽幻想",
    "西幻史诗",
    "黑暗哥特",
    "废土荒凉",
    "赛博霓虹",
    "星际宏伟",
    "民俗志怪",
    "宇宙恐怖",
    "校园青春",
    "市井烟火",
    "工业机械",
    "神秘学仪式"
  ],
  "style_recommendations": {
    "玄幻": [
      "东方古典",
      "盛唐气象",
      "黑暗哥特"
    ],
    "奇幻": [
      "西幻史诗",
      "黑暗哥特",
      "蒸汽幻想",
      "神秘学仪式"
    ],
    "武侠": [
      "东方古典",
      "魏晋风流",
      "市井烟火"
    ],
    "仙侠": [
      "东方古典",
      "魏晋风流",
      "盛唐气象",
      "民俗志怪"
    ],
    "都市": [
      "市井烟火",
      "校园青春",
      "赛博霓虹"
    ],
    "现实": [
      "市井烟火",
      "工业机械"
    ],
    "历史": [
      "东方古典",
      "盛唐气象",
      "工业机械"
    ],
    "军事": [
      "工业机械",
      "废土荒凉"
    ],
    "游戏": [
      "赛博霓虹",
      "星际宏伟"
    ],
    "体育": [
      "校园青春",
      "市井烟火"
    ],
    "科幻": [
      "星际宏伟",
      "赛博霓虹",
      "废土荒凉",
      "宇宙恐怖",
      "工业机械"
    ],
    "诸天无限": [
      "宇宙恐怖",
      "神秘学仪式",
      "废土荒凉"
    ],
    "悬疑": [
      "民俗志怪",
      "黑暗哥特",
      "宇宙恐怖",
      "神秘学仪式"
    ],
    "轻小说": [
      "校园青春",
      "市井烟火",
      "赛博霓虹"
    ],
    "古代言情": [
      "东方古典",
      "民俗志怪",
      "市井烟火"
    ],
    "现代言情": [
      "市井烟火",
      "校园青春"
    ],
    "幻想言情": [
      "神秘学仪式",
      "民俗志怪",
      "西幻史诗",
      "星际宏伟"
    ],
    "仙侠奇缘": [
      "东方古典",
      "魏晋风流",
      "民俗志怪"
    ],
    "玄幻言情": [
      "东方古典",
      "神秘学仪式",
      "西幻史诗"
    ],
    "浪漫青春": [
      "校园青春",
      "市井烟火"
    ],
    "悬疑灵异": [
      "民俗志怪",
      "宇宙恐怖",
      "黑暗哥特"
    ],
    "游戏竞技": [
      "赛博霓虹",
      "校园青春"
    ]
  },
  "genre_profiles": {
    "男频|玄幻": {
      "power_currency_candidates": [
        "境界与修为（升级阶梯）",
        "血脉神通（先天资质）",
        "气运功德（天命加身）",
        "秘宝功法（稀缺资源）"
      ],
      "typical_dilemmas": [
        "捷径与根基：速成留下隐患 vs 稳修被时代抛下",
        "力量与人性：更强一步更非人一步 vs 守住人性受制于人"
      ],
      "reader_expectations": [
        "开局快速立住爽点，小目标兑现勤",
        "升级阶梯清晰，阶段目标可预期",
        "打脸要有实力或信息依据，不无脑碾压"
      ],
      "taboos": [
        "开局大段设定倾泻",
        "主角光环无代价救场",
        "中期力量体系崩坏（越级无解释）"
      ]
    },
    "男频|仙侠": {
      "power_currency_candidates": [
        "境界（炼气至渡劫的阶梯）",
        "寿元（修仙的本质稀缺）",
        "道基与心魔（质量重于速度）",
        "灵石丹药（经济约束）"
      ],
      "typical_dilemmas": [
        "求长生先杀生：夺资源续命 vs 守道心受损",
        "捷径与根基：丹药速成埋心魔 vs 苦修被同辈抛下"
      ],
      "reader_expectations": [
        "修仙秩序自洽（境界/资源/宗门）",
        "凡人起点步步为营的积累感",
        "长生视角下的人情冷暖与代价"
      ],
      "taboos": [
        "现代物理/科学术语无设定依据地混入",
        "境界跳跃无积累支撑",
        "资源无限供给削弱稀缺感"
      ]
    },
    "男频|都市": {
      "power_currency_candidates": [
        "金钱与资本",
        "人脉与信息差",
        "专业能力（行业纵深）",
        "权柄（体制内位置）"
      ],
      "typical_dilemmas": [
        "成功与底线：来路快的钱 vs 良心债",
        "个人跃迁与出身枷锁：往上走要不要回头"
      ],
      "reader_expectations": [
        "行业细节真实有肉",
        "现实社交规则（人情/饭局/潜规则）",
        "逆袭有过程感，非天降横财"
      ],
      "taboos": [
        "悬浮都市（无生活质感）",
        "反派降智送人头",
        "金融/法律等专业细节硬伤"
      ]
    },
    "女频|古代言情": {
      "power_currency_candidates": [
        "礼法与名声（社交货币）",
        "姻亲网络（母族/婆家/夫家）",
        "嫁妆与私产（经济底气）",
        "恩宠与位分"
      ],
      "typical_dilemmas": [
        "生存与体面：守礼吃亏 vs 破规赢一时输根基",
        "真心与算计：婚姻里论爱 vs 论利"
      ],
      "reader_expectations": [
        "宅门/宗法规则细节真实（妾室/嫁妆/立嗣）",
        "女主每步棋有依据",
        "打脸有债权：先被亏待再讨回"
      ],
      "taboos": [
        "白莲花圣母（无底线善良还赢）",
        "报复过额（超出受害授权）",
        "礼法规则前后不一",
        "现代思维无穿越依据地空降"
      ]
    },
    "女频|现代言情": {
      "power_currency_candidates": [
        "事业与经济独立",
        "情感主导权（谁先动心谁被动）",
        "社会身份与马甲",
        "信息与把柄"
      ],
      "typical_dilemmas": [
        "爱情与自我：为爱妥协的边界在哪",
        "亲密与权力：关系里的掌控与让渡"
      ],
      "reader_expectations": [
        "情感线高密度、张力持续",
        "男女主人设立得住不降智",
        "事业线与爱情线互相成就"
      ],
      "taboos": [
        "一句话能解的误会拖十章",
        "男主悬浮霸总化",
        "女主恋爱脑丧失主体性"
      ]
    },
    "女频|幻想言情": {
      "power_currency_candidates": [
        "任务积分与世界跳转权（快穿）",
        "剧情知情权（穿书者信息优势）",
        "规则漏洞（怪谈/无限流）",
        "异能与玄学"
      ],
      "typical_dilemmas": [
        "完成任务 vs 保住本心（系统的代价）",
        "知情者优势与介入伦理：改剧情救谁"
      ],
      "reader_expectations": [
        "单元世界/副本节奏清晰",
        "系统与规则设定自洽",
        "女主主动破局非被动等待"
      ],
      "taboos": [
        "世界切换沦为换皮（人物无成长连续性）",
        "怪谈规则前后矛盾",
        "金手指万能化"
      ]
    }
  },
  "recommendation_rules": {
    "genre_temperaments": {
      "仙侠": [
        "古典",
        "沉潜",
        "执着",
        "坚韧"
      ],
      "体育": [
        "紧张",
        "专业",
        "热血",
        "递进"
      ],
      "军事": [
        "紧张",
        "专业",
        "团队",
        "果决"
      ],
      "历史": [
        "厚重",
        "清醒",
        "耐心",
        "建设"
      ],
      "奇幻": [
        "宏阔",
        "克制",
        "高压",
        "好奇",
        "暗黑"
      ],
      "悬疑": [
        "克制",
        "精确",
        "悬念",
        "内省",
        "智斗"
      ],
      "武侠": [
        "果决",
        "悲壮",
        "正直",
        "古典"
      ],
      "游戏": [
        "幽默",
        "解构",
        "紧张",
        "团队"
      ],
      "玄幻": [
        "宏阔",
        "克制",
        "坚韧",
        "递进",
        "暗黑"
      ],
      "现实": [
        "厚重",
        "清醒",
        "温厚",
        "多视角"
      ],
      "科幻": [
        "冷静",
        "严谨",
        "逻辑",
        "好奇",
        "壮阔"
      ],
      "诸天无限": [
        "高压",
        "坚忍",
        "好奇",
        "解构",
        "暗黑"
      ],
      "轻小说": [
        "明亮/强张力",
        "幽默",
        "解构",
        "温暖",
        "真诚"
      ],
      "都市": [
        "温厚",
        "务实",
        "温暖",
        "细腻",
        "真诚"
      ],
      "古代言情": [
        "厚重",
        "清醒",
        "多视角",
        "细密"
      ],
      "现代言情": [
        "细腻",
        "温厚",
        "真诚",
        "明亮/强张力"
      ],
      "幻想言情": [
        "好奇",
        "解构",
        "高压",
        "智斗"
      ],
      "仙侠奇缘": [
        "古典",
        "沉潜",
        "执着",
        "细腻"
      ],
      "玄幻言情": [
        "宏阔",
        "坚韧",
        "递进"
      ],
      "浪漫青春": [
        "明亮/强张力",
        "真诚",
        "温暖"
      ],
      "悬疑灵异": [
        "悬念",
        "精确",
        "诡谲",
        "智斗"
      ],
      "游戏竞技": [
        "紧张",
        "专业",
        "团队",
        "幽默"
      ]
    },
    "tone_temperaments": {
      "冷峻克制": [
        "冷峻",
        "克制",
        "冷静"
      ],
      "史诗厚重": [
        "宏阔",
        "结构化",
        "厚重"
      ],
      "悬疑紧张": [
        "悬念",
        "精确",
        "智斗",
        "内省"
      ],
      "慢热沉浸": [
        "沉潜",
        "古典",
        "厚重"
      ],
      "沙雕搞笑": [
        "幽默",
        "解构",
        "对话驱动"
      ],
      "温馨治愈": [
        "温暖",
        "细腻",
        "生活流"
      ],
      "热血悲壮": [
        "悲壮",
        "正直",
        "果决"
      ],
      "爽快燃向": [
        "热血",
        "递进",
        "坚韧"
      ],
      "疯癫混乱": [
        "复杂",
        "暗黑",
        "反英雄/恶人"
      ],
      "绝望求生": [
        "高压",
        "坚忍",
        "危机"
      ],
      "轻松欢乐": [
        "幽默",
        "解构",
        "对话驱动"
      ],
      "黑暗压抑": [
        "暗黑",
        "反英雄/恶人",
        "高压",
        "冷峻"
      ],
      "甜宠治愈": [
        "温暖",
        "细腻",
        "生活流"
      ],
      "轻松搞笑": [
        "幽默",
        "解构",
        "对话驱动"
      ],
      "爽文逆袭": [
        "热血",
        "递进",
        "坚韧"
      ],
      "复仇打脸": [
        "智斗",
        "冷峻",
        "压抑"
      ],
      "虐恋情深": [
        "明亮/强张力",
        "细密",
        "宿命"
      ],
      "破镜重圆": [
        "细密",
        "真诚",
        "宿命"
      ],
      "事业成长": [
        "递进",
        "坚韧",
        "务实"
      ],
      "悬疑烧脑": [
        "悬念",
        "精确",
        "智斗"
      ],
      "家国豪情": [
        "厚重",
        "悲壮",
        "宏阔"
      ],
      "疯批张力": [
        "暗黑",
        "复杂",
        "反英雄/恶人"
      ]
    }
  },
  "system_archetypes": [
    {
      "constraint_ref": "novelos://creator-signature/system-epic-framework/1/sha256:2dbe1642ae2893516f1479f2a6840a53dbb62f8edf0fdbb3e56be8d5f8128d5f",
      "display_name": "体系史诗",
      "genre_tags": [
        "玄幻",
        "奇幻",
        "仙侠",
        "科幻"
      ],
      "profile_version_id": "creator-profile-version:system-epic-framework:1",
      "reader_promise": "规则、文明与人物命运彼此咬合",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在规则与时代缝隙中抗争并试图维护秩序的个体"
        ],
        "distrusts": [
          "警惕缺乏约束的个体绝对武力与无代价力量膨胀"
        ],
        "recurring_attention": [
          "持续关注力量体系演进、文明演变与规则背后的代价"
        ],
        "narrative_principles": [
          "遵循力量必有代价与世界体系自我咬合的叙事逻辑"
        ],
        "forbidden_conveniences": [
          "禁止无代价机械降神或凭空打破既定世界法则"
        ],
        "expression_preferences": [
          "偏好宏阔克制、强调结构与因果交织的叙事笔触"
        ],
        "negative_constraints": [
          "不得放弃力量体系的严密性与文明背景的厚重感"
        ]
      },
      "subject_hash": "sha256:2dbe1642ae2893516f1479f2a6840a53dbb62f8edf0fdbb3e56be8d5f8128d5f",
      "temperament_tags": [
        "宏阔",
        "克制",
        "结构化"
      ],
      "channel_affinity": "男频"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-upward-striver/1/sha256:d159c29411854a5e91b881ef6384cbf9addb70f437482ef37687ff31601ba6e5",
      "display_name": "逆境攀登",
      "genre_tags": [
        "玄幻",
        "仙侠",
        "都市",
        "游戏",
        "体育"
      ],
      "profile_version_id": "creator-profile-version:system-upward-striver:1",
      "reader_promise": "低起点人物用选择和代价向上",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理身处微贱却凭借意志与选择顽强向上突破的打拼者"
        ],
        "distrusts": [
          "警惕不劳而获的虚妄幸运与靠血统特权凌驾他人的傲慢"
        ],
        "recurring_attention": [
          "持续关注主角在资源匮乏与重重阶层压制下的生存策略"
        ],
        "narrative_principles": [
          "保持明确的阶段性目标与脚踏实地的能力成长节奏"
        ],
        "forbidden_conveniences": [
          "禁止无理由的越阶碾压或缺乏积累的凭空顿悟"
        ],
        "expression_preferences": [
          "偏好紧凑递进、充满行动张力与爽快回馈的表达风格"
        ],
        "negative_constraints": [
          "不得削弱逆境的真实压迫感与攀登过程的代价感"
        ]
      },
      "subject_hash": "sha256:d159c29411854a5e91b881ef6384cbf9addb70f437482ef37687ff31601ba6e5",
      "temperament_tags": [
        "坚韧",
        "热血",
        "递进"
      ],
      "channel_affinity": "男频"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-honor-in-action/1/sha256:56b27afbd822ca48a0110b59394d4de3e7264831b7a09a2e0919f6b6d141b432",
      "display_name": "侠义行动",
      "genre_tags": [
        "武侠",
        "军事",
        "历史",
        "玄幻"
      ],
      "profile_version_id": "creator-profile-version:system-honor-in-action:1",
      "reader_promise": "行动中辨明责任、尊严与代价",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在乱世或不公中敢于挺身而出、守护底线的行动者"
        ],
        "distrusts": [
          "警惕以大局为名的冷酷牺牲与虚伪的高尚口号"
        ],
        "recurring_attention": [
          "持续关注个体在道德抉择中的行动决策与尊严坚守"
        ],
        "narrative_principles": [
          "强调行动优先、言出必行与承诺带来的不可逆后果"
        ],
        "forbidden_conveniences": [
          "禁止事后妥协逃避责任或用巧合消解道德抉择的重压"
        ],
        "expression_preferences": [
          "偏好干练果决、富有画面感与悲壮宿命感的叙事节奏"
        ],
        "negative_constraints": [
          "不得将侠义降格为无脑莽撞或虚无主义的无差别暴力"
        ]
      },
      "subject_hash": "sha256:56b27afbd822ca48a0110b59394d4de3e7264831b7a09a2e0919f6b6d141b432",
      "temperament_tags": [
        "果决",
        "悲壮",
        "正直"
      ],
      "channel_affinity": "男频"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-community-builder/1/sha256:776fda0b605b1391746141dc5786b19a294bcaa9f12d10ca1e5e6419a8494ec5",
      "display_name": "群像共建",
      "genre_tags": [
        "现实",
        "都市",
        "历史",
        "军事",
        "游戏"
      ],
      "profile_version_id": "creator-profile-version:system-community-builder:1",
      "reader_promise": "分歧中的人走向协作与共同体",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理背景迥异却在共同事业中相互补完的普通建设者"
        ],
        "distrusts": [
          "警惕独夫专断、抹杀个体差异的集权思想与内耗投机"
        ],
        "recurring_attention": [
          "持续关注不同角色的利益诉求、分歧调和与协作机制"
        ],
        "narrative_principles": [
          "遵循群像互补、多视角交织与共同体逐步建立的规律"
        ],
        "forbidden_conveniences": [
          "禁止降智工具人或强行用个人光环掩盖团队合作价值"
        ],
        "expression_preferences": [
          "偏好温厚务实、注重细节刻画与人情世故的多元视角表达"
        ],
        "negative_constraints": [
          "不得抹杀配角的主体性或将共同体建设简单化为一人独舞"
        ]
      },
      "subject_hash": "sha256:776fda0b605b1391746141dc5786b19a294bcaa9f12d10ca1e5e6419a8494ec5",
      "temperament_tags": [
        "温厚",
        "务实",
        "群像"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-rational-inference/1/sha256:ffb1b18a13b124eb53dfe80668d9ce1d59e3d3ca61eef31d39b0b9c0ec5c73b1",
      "display_name": "理性推演",
      "genre_tags": [
        "科幻",
        "历史",
        "游戏",
        "现实"
      ],
      "profile_version_id": "creator-profile-version:system-rational-inference:1",
      "reader_promise": "清晰约束下的意外且必然",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理恪守理性法则、在有限信息中寻找最优解的探求者"
        ],
        "distrusts": [
          "警惕基于情绪化的盲目豪赌与缺乏事实依据的神秘主义"
        ],
        "recurring_attention": [
          "持续关注前提条件设定、因果推演逻辑与推断可回溯性"
        ],
        "narrative_principles": [
          "遵循信息完备、逻辑自洽与情理之中意料之外的解谜原则"
        ],
        "forbidden_conveniences": [
          "禁止临时篡改既有规则或依赖无法推演的降维打法"
        ],
        "expression_preferences": [
          "偏好冷静严谨、条理清晰且富于智力愉悦感的叙事语言"
        ],
        "negative_constraints": [
          "不得出现逻辑漏洞、双标推论或凭空捏造未知前提"
        ]
      },
      "subject_hash": "sha256:ffb1b18a13b124eb53dfe80668d9ce1d59e3d3ca61eef31d39b0b9c0ec5c73b1",
      "temperament_tags": [
        "冷静",
        "严谨",
        "逻辑"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-disaster-survivor/1/sha256:646fb63abcc9a1000c6e1fab4da39ee7872bea6fa91379115528e54d2600ed18",
      "display_name": "灾厄求生",
      "genre_tags": [
        "科幻",
        "奇幻",
        "悬疑",
        "诸天无限"
      ],
      "profile_version_id": "creator-profile-version:system-disaster-survivor:1",
      "reader_promise": "极端压力下守住人性与判断",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在灾难与绝境中顽强求生并守住理智底线的幸存者"
        ],
        "distrusts": [
          "警惕危机中的盲目恐慌、道德绑架与毫无人性的极端利己"
        ],
        "recurring_attention": [
          "持续关注资源枯竭限制、危机环境压迫与求生抉择代价"
        ],
        "narrative_principles": [
          "保持高压危机感、严苛的资源消耗规则与不可逆的环境变化"
        ],
        "forbidden_conveniences": [
          "禁止无尽物资供给或在致命危机中强行安排安全庇护"
        ],
        "expression_preferences": [
          "偏好紧张扣人心弦、侧重生动感官体验与高压心理的描写"
        ],
        "negative_constraints": [
          "不得削弱生存危机的真实威胁或消解绝境中的人道底线"
        ]
      },
      "subject_hash": "sha256:646fb63abcc9a1000c6e1fab4da39ee7872bea6fa91379115528e54d2600ed18",
      "temperament_tags": [
        "高压",
        "坚忍",
        "危机"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-fair-truth/1/sha256:9bbcc6e2dd0a914f8e1fdb6c9972e09c1aba0f1a7e973939be09b63349826fc5",
      "display_name": "公平求真",
      "genre_tags": [
        "悬疑",
        "都市",
        "历史",
        "现实"
      ],
      "profile_version_id": "creator-profile-version:system-fair-truth:1",
      "reader_promise": "真相来自可回溯线索与动机",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理不畏迷雾与压力、坚持追寻客观事实真相的追查者"
        ],
        "distrusts": [
          "警惕主观先入为主的偏见、权力掩盖真相与伪造证据"
        ],
        "recurring_attention": [
          "持续关注线索链条完整性、动机合理性与证据闭环过程"
        ],
        "narrative_principles": [
          "遵循公平悬疑原则，所有关键线索必须对读者公开回溯"
        ],
        "forbidden_conveniences": [
          "禁止临近结尾隐瞒核心线索或用超自然理由解释犯罪"
        ],
        "expression_preferences": [
          "偏好克制精确、注重线索铺垫与推理反转的悬念表达"
        ],
        "negative_constraints": [
          "不得破坏线索与真相的公平对等关系或依赖天降巧合破案"
        ]
      },
      "subject_hash": "sha256:9bbcc6e2dd0a914f8e1fdb6c9972e09c1aba0f1a7e973939be09b63349826fc5",
      "temperament_tags": [
        "克制",
        "精确",
        "悬念"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-folklore-echo/1/sha256:a32508aeb21011a581c0be7eba436de5c1f0ec11521f8d92676dc145d9fdadc4",
      "display_name": "民俗幽微",
      "genre_tags": [
        "悬疑",
        "奇幻",
        "仙侠",
        "武侠"
      ],
      "profile_version_id": "creator-profile-version:system-folklore-echo:1",
      "reader_promise": "异常与日常交织，恐惧背后有人情",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理被困于奇异规约、古老习俗或悲剧宿命中的幽微众生"
        ],
        "distrusts": [
          "警惕粗暴破坏民俗秩序的狂妄武断与缺乏悲悯的猎奇心态"
        ],
        "recurring_attention": [
          "持续关注民间志怪传说、地方规约与古老恐惧背后的执念"
        ],
        "narrative_principles": [
          "遵循日常与奇诡交织、异象映射人心欲望与情感的原则"
        ],
        "forbidden_conveniences": [
          "禁止用纯物理暴力粗暴抹杀具有文化内涵的奇异现象"
        ],
        "expression_preferences": [
          "偏好具诗性氛围、诡谲幽深且富有中式悲悯色彩的文风"
        ],
        "negative_constraints": [
          "不得沦为毫无人文情怀的廉价吓人或脱离地方风土的空洞怪谈"
        ]
      },
      "subject_hash": "sha256:a32508aeb21011a581c0be7eba436de5c1f0ec11521f8d92676dc145d9fdadc4",
      "temperament_tags": [
        "诗性",
        "诡谲",
        "悲悯"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-institutional-lens/1/sha256:cd58553f354c67e06e4790d037f455b7956873b52b366c6fd50fb95333cf3ff2",
      "display_name": "制度观察",
      "genre_tags": [
        "历史",
        "现实",
        "都市",
        "军事"
      ],
      "profile_version_id": "creator-profile-version:system-institutional-lens:1",
      "reader_promise": "个体命运在资源与时代中变化",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在体制、结构与时代浪潮中挣扎浮沉并试图破局的思考者"
        ],
        "distrusts": [
          "警惕将复杂社会历史问题简单化归咎于个别恶人的幼稚观"
        ],
        "recurring_attention": [
          "持续关注资源分配博弈、权力运行机制与结构性困境演变"
        ],
        "narrative_principles": [
          "遵循制度决定利益、利益驱动行为与时代重塑个体命运的逻辑"
        ],
        "forbidden_conveniences": [
          "禁止靠主角个人口号瞬间改变千年积累的利益结构"
        ],
        "expression_preferences": [
          "偏好厚重清醒、多视角穿透与深刻洞察社会机理的笔法"
        ],
        "negative_constraints": [
          "不得忽视制度与环境对人物行为的深层塑造力"
        ]
      },
      "subject_hash": "sha256:cd58553f354c67e06e4790d037f455b7956873b52b366c6fd50fb95333cf3ff2",
      "temperament_tags": [
        "厚重",
        "清醒",
        "多视角"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-everyday-repair/1/sha256:1be638ad224eecffecf40c4b65e6a8f55dbc665adbb1acacc4f940ad0a2889ee",
      "display_name": "市井治愈",
      "genre_tags": [
        "都市",
        "现实",
        "轻小说"
      ],
      "profile_version_id": "creator-profile-version:system-everyday-repair:1",
      "reader_promise": "平凡关系里的修复、成长与互助",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在日常生活中承受微小创伤却依然善待他人的平凡人"
        ],
        "distrusts": [
          "警惕虚无冷漠的社会疏离感与刻意制造无意义痛苦的恶趣"
        ],
        "recurring_attention": [
          "持续关注生活细琐温情、美食手艺与人与人之间的微小修复"
        ],
        "narrative_principles": [
          "遵循生活流叙事、通过微观互动展现心理疗愈与关系成长"
        ],
        "forbidden_conveniences": [
          "禁止突然插入恶俗狗血冲突或破坏温馨生活基调的恶性事件"
        ],
        "expression_preferences": [
          "偏好温暖细腻、富有生活气息与治愈人心的轻松语调"
        ],
        "negative_constraints": [
          "不得滑向浮夸虚假的工业糖精或空洞无物的水字数日常"
        ]
      },
      "subject_hash": "sha256:1be638ad224eecffecf40c4b65e6a8f55dbc665adbb1acacc4f940ad0a2889ee",
      "temperament_tags": [
        "温暖",
        "细腻",
        "生活流"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-youthful-bonds/1/sha256:2de96156a4a393d4fe0fb38c9f2737c5a8d97b1d32b1ed56416312714b2e2095",
      "display_name": "青春与情感羁绊",
      "genre_tags": [
        "轻小说",
        "都市",
        "现实",
        "体育"
      ],
      "profile_version_id": "creator-profile-version:system-youthful-bonds:1",
      "reader_promise": "年轻人在关系、情感拉扯、梦想与自我中长成",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在青春迷茫、情感博弈与宿命羁绊中勇敢追寻自我的年轻心灵"
        ],
        "distrusts": [
          "警惕功利算计亲密关系、玩弄情感与对真诚承诺的轻蔑"
        ],
        "recurring_attention": [
          "持续关注人物间的情感张力、关系拉扯、双向救赎与自我确认"
        ],
        "narrative_principles": [
          "遵循情感博弈自洽、关系演进有据与梦想与羁绊双向提振"
        ],
        "forbidden_conveniences": [
          "禁止无缘由的降智误会或缺乏情感积淀的硬凑亲密"
        ],
        "expression_preferences": [
          "偏好情感充沛、富于心理拉扯张力与明亮真诚的表达笔致"
        ],
        "negative_constraints": [
          "不得剥离情感博弈中的真诚性或将青春关系降格为低俗套路"
        ]
      },
      "subject_hash": "sha256:2de96156a4a393d4fe0fb38c9f2737c5a8d97b1d32b1ed56416312714b2e2095",
      "temperament_tags": [
        "明亮/强张力",
        "真诚",
        "宿命"
      ],
      "channel_affinity": "女频"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-contrast-adventure/1/sha256:f4650e926b321291aa6093b83adc546e6ef7512e712cb5f0eb07e045b10458ee",
      "display_name": "反差与荒诞解构",
      "genre_tags": [
        "游戏",
        "轻小说",
        "都市",
        "诸天无限"
      ],
      "profile_version_id": "creator-profile-version:system-contrast-adventure:1",
      "reader_promise": "严肃目标与轻快日常/荒诞吐槽彼此提振",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在沉重世界观下依然保持乐观吐槽、用反差与荒诞解构严肃的旅人"
        ],
        "distrusts": [
          "警惕死板教条的陈词滥调与缺乏幽默感、自以为是的说教"
        ],
        "recurring_attention": [
          "持续关注严肃设定的反差呈现、吐槽解构与轻快喜剧效果"
        ],
        "narrative_principles": [
          "遵循反差解构有度、对话诙谐风趣与主线目标不失衡的原则"
        ],
        "forbidden_conveniences": [
          "禁止无底线的滥用恶搞导致世界观彻底崩塌或主线丧失吸引力"
        ],
        "expression_preferences": [
          "偏好对话驱动、节奏明快、充满机智吐槽与反差萌点的语言"
        ],
        "negative_constraints": [
          "不得因荒诞解构而消解核心目标的严肃性或沦为低俗烂梗堆砌"
        ]
      },
      "subject_hash": "sha256:f4650e926b321291aa6093b83adc546e6ef7512e712cb5f0eb07e045b10458ee",
      "temperament_tags": [
        "幽默",
        "解构",
        "对话驱动"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-shadowed-choice/1/sha256:ab8c8faf8bdb09071e425060eed4920733be1c04e6b4d40e282ece676a647855",
      "display_name": "暗影与暗黑博弈",
      "genre_tags": [
        "奇幻",
        "玄幻",
        "悬疑",
        "诸天无限"
      ],
      "profile_version_id": "creator-profile-version:system-shadowed-choice:1",
      "reader_promise": "没有完美选项，主角以利己/灰色选择承担后果与黑洞",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在残酷黑洞秩序中以利己算计、暗黑手段生存并承担道德后果的行者"
        ],
        "distrusts": [
          "警惕虚伪的道德圣母口号与毫无准备的盲目善意给自身带来的毁灭"
        ],
        "recurring_attention": [
          "持续关注灰色抉择代价、暗黑人性博弈与利益最大化算计"
        ],
        "narrative_principles": [
          "遵循暗黑生存法则、冷酷代价计算与反英雄/恶人选择的不可逆后果"
        ],
        "forbidden_conveniences": [
          "禁止天降正义道德救赎或靠天真善意无伤化解黑暗博弈"
        ],
        "expression_preferences": [
          "偏好冷峻硬朗、直面人性暗面与充满生存博弈张力的笔法"
        ],
        "negative_constraints": [
          "不得用正派道德框架阉割主角的利己算计或掩盖暗黑博弈的残酷性"
        ]
      },
      "subject_hash": "sha256:ab8c8faf8bdb09071e425060eed4920733be1c04e6b4d40e282ece676a647855",
      "temperament_tags": [
        "冷峻",
        "暗黑",
        "复杂",
        "反英雄/恶人"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-restoration-craft/1/sha256:9bee2dd5953a403d12e944d47ea430bfbb3c20c4c1845d9caa484628e5bf2214",
      "display_name": "经营复兴",
      "genre_tags": [
        "历史",
        "都市",
        "仙侠",
        "游戏"
      ],
      "profile_version_id": "creator-profile-version:system-restoration-craft:1",
      "reader_promise": "用资源、技艺和关系重建衰败之地",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理依靠专业技艺、资源整合与耐心经营让衰败事物重焕生机的建设者"
        ],
        "distrusts": [
          "警惕掠夺破产式投机与破坏生产力成果的掠夺行为"
        ],
        "recurring_attention": [
          "持续关注产业资源流转、技术细节突破与积累式建设成就感"
        ],
        "narrative_principles": [
          "遵循积累递进、技艺出真知与经营复兴符合经济逻辑的规律"
        ],
        "forbidden_conveniences": [
          "禁止凭空变出无限资源或无视生产规律的瞬间神迹"
        ],
        "expression_preferences": [
          "偏好耐心扎实、富于专业细节与获得感满满的表达方式"
        ],
        "negative_constraints": [
          "不得脱离物理与经济建设规律或将复兴过程敷衍化处理"
        ]
      },
      "subject_hash": "sha256:9bee2dd5953a403d12e944d47ea430bfbb3c20c4c1845d9caa484628e5bf2214",
      "temperament_tags": [
        "耐心",
        "建设",
        "成就"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-tactical-teamwork/1/sha256:3ed5e47396c0cf450b5f78db08817076b66c66aa3f86e58a71939f5a8c885015",
      "display_name": "战术协作",
      "genre_tags": [
        "军事",
        "体育",
        "游戏",
        "科幻"
      ],
      "profile_version_id": "creator-profile-version:system-tactical-teamwork:1",
      "reader_promise": "胜利来自信息、配合和临场判断",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在战术博弈中高度信任队友、依靠信息与执行力克敌的专业团队"
        ],
        "distrusts": [
          "警惕脱离团队配合的个人英雄主义与违背战术常识的蛮干"
        ],
        "recurring_attention": [
          "持续关注战场/赛场信息差、团队分工配合与临场决策修正"
        ],
        "narrative_principles": [
          "遵循战术自洽、专业配合胜于单打独斗与信息即胜负的原则"
        ],
        "forbidden_conveniences": [
          "禁止忽视战术阵型与指挥系统而靠个人爆种无伤翻盘"
        ],
        "expression_preferences": [
          "偏好节奏紧密、专业术语准确且充满团队热血感的叙事节奏"
        ],
        "negative_constraints": [
          "不得违背战术推演逻辑或将团队成员降级为背景板"
        ]
      },
      "subject_hash": "sha256:3ed5e47396c0cf450b5f78db08817076b66c66aa3f86e58a71939f5a8c885015",
      "temperament_tags": [
        "紧张",
        "专业",
        "团队"
      ],
      "channel_affinity": "男频"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-civilization-voyage/1/sha256:d0d40597bb5d271e7e58bc1f4727ca27398b3eb813bd5ec7befccf75da868c6a",
      "display_name": "文明远航",
      "genre_tags": [
        "科幻",
        "奇幻",
        "诸天无限"
      ],
      "profile_version_id": "creator-profile-version:system-civilization-voyage:1",
      "reader_promise": "探索未知并追问文明如何延续",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理怀抱好奇心与敬畏感、踏入未知星空/秘境探索文明未来的远航者"
        ],
        "distrusts": [
          "警惕傲慢的文明征服欲与因无知恐惧而产生的毁灭性排他心理"
        ],
        "recurring_attention": [
          "持续关注异质文明形态、宏大宇宙景观与文明延续的哲学思考"
        ],
        "narrative_principles": [
          "遵循探索未知的壮阔好奇感、文明碰撞逻辑与敬畏自然的原则"
        ],
        "forbidden_conveniences": [
          "禁止将未知文明浅薄化为低级怪兽或凭空忽视宏大空间尺度"
        ],
        "expression_preferences": [
          "偏好壮阔好奇、富于诗意想象与宇宙史诗感的大气笔触"
        ],
        "negative_constraints": [
          "不得削弱宇宙与未知的宏伟尺度或将文明远航降格为狭隘争斗"
        ]
      },
      "subject_hash": "sha256:d0d40597bb5d271e7e58bc1f4727ca27398b3eb813bd5ec7befccf75da868c6a",
      "temperament_tags": [
        "好奇",
        "壮阔",
        "探索"
      ],
      "channel_affinity": "男频"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-psychological-maze/1/sha256:c01bff9a51e7d275db88af1e84b14b685495e03e0a60afca9b6828460e610b06",
      "display_name": "心理迷宫与人性博弈",
      "genre_tags": [
        "悬疑",
        "现实",
        "都市",
        "轻小说"
      ],
      "profile_version_id": "creator-profile-version:system-psychological-maze:1",
      "reader_promise": "外部谜题与智斗映照创伤、欲望、算计与人性黑洞",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在人性黑洞、心理防线博弈与自我创伤中苦苦智斗的探寻者"
        ],
        "distrusts": [
          "警惕虚饰的人性假象、心理操纵与自我欺骗带来的毁灭风险"
        ],
        "recurring_attention": [
          "持续关注人心隐秘欲望、算计试探、心理死局与人性博弈细节"
        ],
        "narrative_principles": [
          "遵循心理自洽、智斗防线拉扯与外部谜题映射内心深渊的原则"
        ],
        "forbidden_conveniences": [
          "禁止粗暴的口号式心理救赎或忽视心理防线突兀反转"
        ],
        "expression_preferences": [
          "偏好细密内省、充满心理悬念张力与人性幽微剖析的笔感"
        ],
        "negative_constraints": [
          "不得浅薄化人性复杂博弈或用粗暴解法消解心理死局的深度"
        ]
      },
      "subject_hash": "sha256:c01bff9a51e7d275db88af1e84b14b685495e03e0a60afca9b6828460e610b06",
      "temperament_tags": [
        "内省",
        "压抑",
        "智斗",
        "细密"
      ],
      "channel_affinity": "通吃"
    },
    {
      "constraint_ref": "novelos://creator-signature/system-fate-cultivation/1/sha256:f6b1963e0f5eef8c57a311b9eb5a486252bd084acbf0fc6d6a3975563cfe302e",
      "display_name": "宿命修行",
      "genre_tags": [
        "仙侠",
        "玄幻",
        "武侠",
        "奇幻"
      ],
      "profile_version_id": "creator-profile-version:system-fate-cultivation:1",
      "reader_promise": "以修行、承诺和选择改变既定秩序",
      "revision": 1,
      "signature": {
        "schema_version": 1,
        "sympathies": [
          "同理在天道宿命压制下沉潜修心、以执念与承诺向死而生的修行者"
        ],
        "distrusts": [
          "警惕顺从宿命天道的虚无主义与背弃初心承诺的投机求存"
        ],
        "recurring_attention": [
          "持续关注道心磨砺、宿命枷锁对抗与古朴承诺的兑现代价"
        ],
        "narrative_principles": [
          "遵循修心即修道、选择重于天赋与承诺重于生死的古典韵味"
        ],
        "forbidden_conveniences": [
          "禁止脱离心性修持的投机突破或无代价改变既定天命"
        ],
        "expression_preferences": [
          "偏好古典沉潜、含蓄隽永且富于哲理意味的文言韵味表达"
        ],
        "negative_constraints": [
          "不得剥离修行的道心修持本质或将宿命对抗浅薄化为快餐升级"
        ]
      },
      "subject_hash": "sha256:f6b1963e0f5eef8c57a311b9eb5a486252bd084acbf0fc6d6a3975563cfe302e",
      "temperament_tags": [
        "古典",
        "沉潜",
        "执着"
      ],
      "channel_affinity": "男频"
    }
  ]
};
