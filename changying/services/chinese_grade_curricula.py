"""小学语文 3、4、6 年级通用知识地图、10 类题型题库与四大板块应试专项.

设计原则：
- 保持 4 大知识域 id 与五年级一致（words 字词与语音、sentence 句子与修辞、poetry 古诗文与积累、reading 阅读方法与表达）。
- 每个年级 4 域 × 4 节点 = 16 个节点，每个节点配备至少 6 道高质量题目，全面覆盖 10 类语文题型：
  - 地图轻辅助：basic_choice、hanzi_tiles、poem_tiles、error_spot、sentence_choice、reading_choice
  - 专项强应试：dictation_spell、poem_fill、reading_short、micro_writing
- 年龄段交互适配数据：
  - dictation_spell 与 poem_fill 题提供 assistTiles（打乱的候选汉字列表，包含答案全部汉字 + 3~4 个形近干扰字）。
  - micro_writing 与 reading_short 题提供 scaffolds（3~4 个好词锦囊或开头句式支架），minChars 按年级设定（G3 micro_writing 为 35，G4 为 50，G5 为 70，G6 为 85；reading_short 为 10~18）。
- 音频复用已离线生成的确定性静态普通话 MP3，确保离线环境与测试 100% 稳定。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

LEVEL_LABELS = {"basic": "基础", "medium": "中等", "hard": "提高"}

TYPE_POINTS = {
    "basic_choice": 2,
    "hanzi_tiles": 2,
    "dictation_spell": 3,
    "poem_tiles": 2,
    "poem_fill": 3,
    "error_spot": 2,
    "sentence_choice": 2,
    "reading_choice": 2,
    "reading_short": 4,
    "micro_writing": 6,
}

TYPE_LABELS = {
    "basic_choice": "字词辨析",
    "hanzi_tiles": "字块拼词",
    "dictation_spell": "听写拼词",
    "poem_tiles": "点选默写",
    "poem_fill": "精准默写",
    "error_spot": "病句找茬",
    "sentence_choice": "句子修辞",
    "reading_choice": "阅读赏析",
    "reading_short": "阅读简答",
    "micro_writing": "微片段写作",
}

CHINESE_DOMAINS: list[dict[str, Any]] = [
    {"id": "words", "name": "字词与语音", "icon": "🔤", "color": "#a8101c"},
    {"id": "sentence", "name": "句子与修辞", "icon": "✍️", "color": "#0b8f5a"},
    {"id": "poetry", "name": "古诗文与积累", "icon": "📜", "color": "#b45309"},
    {"id": "reading", "name": "阅读方法与表达", "icon": "📖", "color": "#1e4e79"},
]

# ---------------- 三年级 (G3) 16 节点 ----------------
CHINESE_G3_NODES: list[dict[str, Any]] = [
    # words 字词与语音
    {"key": "G3-C1-1", "name": "声韵母与多音字易错读音", "domain": "words", "icon": "🗣️", "grade": 3},
    {"key": "G3-C1-2", "name": "偏旁部首与形近字辨析", "domain": "words", "icon": "🔎", "grade": 3},
    {"key": "G3-C1-3", "name": "ABB/AABB与四字词语积累", "domain": "words", "icon": "🏮", "grade": 3},
    {"key": "G3-C1-4", "name": "听写与看拼音写词语", "domain": "words", "icon": "🎧", "grade": 3},
    # sentence 句子与修辞
    {"key": "G3-C2-1", "name": "把字句与被字句转换", "domain": "sentence", "icon": "🔄", "grade": 3},
    {"key": "G3-C2-2", "name": "比喻句与拟人句识别", "domain": "sentence", "icon": "✨", "grade": 3},
    {"key": "G3-C2-3", "name": "提示语位置与标点符号", "domain": "sentence", "icon": "💬", "grade": 3},
    {"key": "G3-C2-4", "name": "常见简单病句诊断", "domain": "sentence", "icon": "🩺", "grade": 3},
    # poetry 古诗文与积累
    {"key": "G3-C3-1", "name": "三年级写景名篇（《望天门山》《山行》《饮湖上初晴后雨》）", "domain": "poetry", "icon": "🏞️", "grade": 3},
    {"key": "G3-C3-2", "name": "传统节日与儿童古诗（《元日》《九月九日忆山东兄弟》《所见》）", "domain": "poetry", "icon": "🎏", "grade": 3},
    {"key": "G3-C3-3", "name": "启蒙小古文（《司马光》《守株待兔》）", "domain": "poetry", "icon": "📖", "grade": 3},
    {"key": "G3-C3-4", "name": "气象谚语与格言积累", "domain": "poetry", "icon": "🌤️", "grade": 3},
    # reading 阅读方法与表达
    {"key": "G3-C4-1", "name": "找中心句与概括段意", "domain": "reading", "icon": "🎯", "grade": 3},
    {"key": "G3-C4-2", "name": "童话寓言阅读与道理体会", "domain": "reading", "icon": "🧚", "grade": 3},
    {"key": "G3-C4-3", "name": "自然景物与动植物观察阅读", "domain": "reading", "icon": "🌿", "grade": 3},
    {"key": "G3-C4-4", "name": "观察写话与50字微段落表达", "domain": "reading", "icon": "🖋️", "grade": 3},
]

# ---------------- 四年级 (G4) 16 节点 ----------------
CHINESE_G4_NODES: list[dict[str, Any]] = [
    # words 字词与语音
    {"key": "G4-C1-1", "name": "多音字语境辨音与易误读字", "domain": "words", "icon": "🗣️", "grade": 4},
    {"key": "G4-C1-2", "name": "形声字与易错字形辨析", "domain": "words", "icon": "🔎", "grade": 4},
    {"key": "G4-C1-3", "name": "神话与历史故事成语", "domain": "words", "icon": "🏮", "grade": 4},
    {"key": "G4-C1-4", "name": "听写与看拼音写词语", "domain": "words", "icon": "🎧", "grade": 4},
    # sentence 句子与修辞
    {"key": "G4-C2-1", "name": "条件因果转折关联词运用", "domain": "sentence", "icon": "🔗", "grade": 4},
    {"key": "G4-C2-2", "name": "反问句与陈述句转换", "domain": "sentence", "icon": "🔄", "grade": 4},
    {"key": "G4-C2-3", "name": "设问排比与连续动作描写", "domain": "sentence", "icon": "✨", "grade": 4},
    {"key": "G4-C2-4", "name": "病句修改（搭配不当与成分残缺）", "domain": "sentence", "icon": "🩺", "grade": 4},
    # poetry 古诗文与积累
    {"key": "G4-C3-1", "name": "山水田园与哲理古诗（《题西林壁》《暮江吟》《宿新市徐公店》）", "domain": "poetry", "icon": "🏞️", "grade": 4},
    {"key": "G4-C3-2", "name": "边塞与送别古诗（《出塞》《凉州词》《芙蓉楼送辛渐》）", "domain": "poetry", "icon": "🚩", "grade": 4},
    {"key": "G4-C3-3", "name": "神话与劝学小古文（《精卫填海》《王戎不取道旁李》《囊萤夜读》）", "domain": "poetry", "icon": "📖", "grade": 4},
    {"key": "G4-C3-4", "name": "八字成语与名言警句", "domain": "poetry", "icon": "💬", "grade": 4},
    # reading 阅读方法与表达
    {"key": "G4-C4-1", "name": "起因经过结果概括主要内容", "domain": "reading", "icon": "🎯", "grade": 4},
    {"key": "G4-C4-2", "name": "批注阅读与多角度提问策略", "domain": "reading", "icon": "📝", "grade": 4},
    {"key": "G4-C4-3", "name": "人物连续动作与神态心理体会", "domain": "reading", "icon": "❤️", "grade": 4},
    {"key": "G4-C4-4", "name": "细节升格与80字微片段写作", "domain": "reading", "icon": "🖋️", "grade": 4},
]

# ---------------- 六年级 (G6) 16 节点 ----------------
CHINESE_G6_NODES: list[dict[str, Any]] = [
    # words 字词与语音
    {"key": "G6-C1-1", "name": "小升初高频多音字与易错读音", "domain": "words", "icon": "🗣️", "grade": 6},
    {"key": "G6-C1-2", "name": "同音字形近字综合辨析", "domain": "words", "icon": "🔎", "grade": 6},
    {"key": "G6-C1-3", "name": "成语感情色彩与熟语运用", "domain": "words", "icon": "🏮", "grade": 6},
    {"key": "G6-C1-4", "name": "小升初高阶听写与看拼音写词", "domain": "words", "icon": "🎧", "grade": 6},
    # sentence 句子与修辞
    {"key": "G6-C2-1", "name": "复杂复句与关联词综合", "domain": "sentence", "icon": "🔗", "grade": 6},
    {"key": "G6-C2-2", "name": "病句综合诊治（两面对一面/句式杂糅/语序）", "domain": "sentence", "icon": "🩺", "grade": 6},
    {"key": "G6-C2-3", "name": "直述转述与双重否定句转换", "domain": "sentence", "icon": "🔄", "grade": 6},
    {"key": "G6-C2-4", "name": "修辞综合赏析与标点精析", "domain": "sentence", "icon": "✨", "grade": 6},
    # poetry 古诗文与积累
    {"key": "G6-C3-1", "name": "写景咏物名篇（《宿建德江》《六月二十七日望湖楼醉书》《石灰吟》《竹石》）", "domain": "poetry", "icon": "🏞️", "grade": 6},
    {"key": "G6-C3-2", "name": "家国情怀与宋词元曲（《西江月·夜行黄沙道中》《过故人庄》《七律·长征》）", "domain": "poetry", "icon": "🚩", "grade": 6},
    {"key": "G6-C3-3", "name": "经典文言文（《伯牙鼓琴》《书戴嵩画牛》《学弈》《两小儿辩日》）", "domain": "poetry", "icon": "📖", "grade": 6},
    {"key": "G6-C3-4", "name": "传统文化常识与名联警句", "domain": "poetry", "icon": "💬", "grade": 6},
    # reading 阅读方法与表达
    {"key": "G6-C4-1", "name": "点面结合与环境描写作用", "domain": "reading", "icon": "🎯", "grade": 6},
    {"key": "G6-C4-2", "name": "小说人物形象与文章主旨提炼", "domain": "reading", "icon": "❤️", "grade": 6},
    {"key": "G6-C4-3", "name": "非连续性文本与多材料整合", "domain": "reading", "icon": "📊", "grade": 6},
    {"key": "G6-C4-4", "name": "小升初审题立意与100字高分微写作", "domain": "reading", "icon": "🖋️", "grade": 6},
]

NODES_BY_GRADE: dict[int, list[dict[str, Any]]] = {
    3: CHINESE_G3_NODES,
    4: CHINESE_G4_NODES,
    6: CHINESE_G6_NODES,
}


def make_audio_id(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> str:
    raw = f"{voice}|{text.strip()}".encode("utf-8")
    return "zh_" + hashlib.sha1(raw).hexdigest()[:14]


def _shuffle_deterministic(items: list[str], seed: int) -> list[str]:
    out = list(items)
    n = len(out)
    for i in range(n - 1, 0, -1):
        j = (seed * 29 + i * 13 + 5) % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def _strip_punct_chars(s: str) -> str:
    return re.sub(r"[\s，。！？、；：“”‘’\"',.!?;:（）()《》\-—]", "", str(s or "").strip())


def build_assist_tiles(answer: str, distractors: list[str] | None = None, seed: int = 7) -> list[str]:
    """为 dictation_spell 与 poem_fill 构建打乱的候选汉字列表（含答案全部汉字 + 3~4 个形近干扰字）."""
    clean_chars = list(_strip_punct_chars(answer))
    default_pool = ["清", "青", "情", "晴", "辨", "辩", "峰", "锋", "幕", "慕", "燥", "躁"]
    extra: list[str] = []
    if distractors:
        for ch in distractors:
            c = _strip_punct_chars(ch)
            if c and c not in clean_chars and c not in extra:
                extra.append(c[0])
    for ch in default_pool:
        if len(extra) >= 4:
            break
        if ch not in clean_chars and ch not in extra:
            extra.append(ch)
    combined = clean_chars + extra[:4]
    return _shuffle_deterministic(combined, seed + len(combined))


def _infer_grade(node_key: str) -> int:
    k = str(node_key or "").upper()
    if k.startswith("G3-"):
        return 3
    if k.startswith("G4-"):
        return 4
    if k.startswith("G6-"):
        return 6
    return 5


def _q(
    qid: str,
    node_key: str,
    qtype: str,
    level: str,
    text: str,
    answer: str,
    explanation: str,
    *,
    grade: int | None = None,
    options: list[str] | None = None,
    correct_index: int | None = None,
    audio_text: str | None = None,
    audio_voice: str = "zh-CN-XiaoxiaoNeural",
    hint: str = "",
    tiles: list[str] | None = None,
    assist_tiles: list[str] | None = None,
    distractors: list[str] | None = None,
    passage: str | None = None,
    rubric_keywords: list[list[str]] | None = None,
    min_chars: int = 0,
    sample_answer: str = "",
    scaffolds: list[str] | None = None,
) -> dict[str, Any]:
    g = grade if grade is not None else _infer_grade(node_key)
    item: dict[str, Any] = {
        "id": qid,
        "nodeKey": node_key,
        "grade": g,
        "questionType": qtype,
        "typeLabel": TYPE_LABELS.get(qtype, qtype),
        "level": level,
        "levelLabel": LEVEL_LABELS.get(level, level),
        "marks": TYPE_POINTS.get(qtype, 2),
        "text": text,
        "answer": answer,
        "explanation": explanation,
    }
    if options is not None:
        item["options"] = list(options)
        item["correctIndex"] = int(correct_index or 0)
    if audio_text:
        aid = make_audio_id(audio_text, audio_voice)
        item["audioId"] = aid
        item["audioUrl"] = f"/assets/chinese-audio/{aid}.mp3"
        item["audioText"] = audio_text
        item["audioVoice"] = audio_voice
    if hint:
        item["hint"] = hint
    if tiles is not None:
        item["tiles"] = list(tiles)
    if qtype in ("dictation_spell", "poem_fill"):
        if assist_tiles is not None:
            item["assistTiles"] = list(assist_tiles)
        else:
            seed_val = sum(ord(c) for c in qid)
            item["assistTiles"] = build_assist_tiles(answer, distractors, seed=seed_val)
    if passage:
        item["passage"] = passage
    if rubric_keywords:
        item["rubricKeywords"] = [list(grp) for grp in rubric_keywords]
    if min_chars:
        item["minChars"] = int(min_chars)
    elif qtype == "micro_writing":
        item["minChars"] = {3: 35, 4: 50, 5: 70, 6: 85}.get(g, 50)
    elif qtype == "reading_short":
        item["minChars"] = {3: 10, 4: 12, 5: 15, 6: 18}.get(g, 12)
    if sample_answer:
        item["sampleAnswer"] = sample_answer
    if qtype in ("micro_writing", "reading_short"):
        if scaffolds:
            item["scaffolds"] = list(scaffolds)
        else:
            item["scaffolds"] = [
                "答题支架：先点明文中核心细节或画面，再写出体会到的品质或道理",
                "好词锦囊：生动形象、真挚感人、活灵活现、耐人寻味",
                "句式参考：从“……”这一细节中，我体会到了……",
            ]
    return item


def _hanzi_tile_q(
    qid: str,
    node_key: str,
    level: str,
    word: str,
    pinyin: str,
    distractors: list[str],
    explanation: str,
    seed: int = 1,
    audio_text: str | None = None,
) -> dict[str, Any]:
    chars = list(word) + list(distractors)
    tiles = _shuffle_deterministic(chars, seed + len(word))
    return _q(
        qid,
        node_key,
        "hanzi_tiles",
        level,
        f"根据拼音「{pinyin}」，点击字块拼出正确词语：",
        word,
        explanation,
        tiles=tiles,
        hint=f"共 {len(word)} 个字",
        audio_text=audio_text,
    )


def _poem_tile_q(
    qid: str,
    node_key: str,
    level: str,
    prompt: str,
    line: str,
    distractors: list[str],
    explanation: str,
    audio_text: str | None = None,
    seed: int = 1,
) -> dict[str, Any]:
    chars = list(line) + list(distractors)
    tiles = _shuffle_deterministic(chars, seed + len(line))
    return _q(
        qid,
        node_key,
        "poem_tiles",
        level,
        prompt,
        line,
        explanation,
        tiles=tiles,
        hint=f"点击字块按顺序拼出 {len(line)} 个字",
        audio_text=audio_text,
        audio_voice="zh-CN-YunxiNeural",
    )


def _build_g3_questions() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in CHINESE_G3_NODES}

    # G3-C1-1 声韵母与多音字易错读音
    bank["G3-C1-1"] = [
        _q("g3-c11-1", "G3-C1-1", "basic_choice", "basic",
           "“放假”中“假”的正确读音是哪一项？", "jià",
           "表示按照规定暂停工作或学习的时间读 jià，如放假、假日；表示不真实读 jiǎ。",
           options=["jiǎ", "jià", "xiá", "jiā"], correct_index=1),
        _q("g3-c11-2", "G3-C1-1", "basic_choice", "basic",
           "“衣裳”中“裳”在口语词尾应读作：", "shang（轻声）",
           "“衣裳”的“裳”读轻声 shang；在古诗“霓裳”中读 cháng。",
           options=["shāng", "shang（轻声）", "cháng", "shǎng"], correct_index=1),
        _q("g3-c11-3", "G3-C1-1", "basic_choice", "medium",
           "“大家围成一个圆圈”中“圈”的正确读音是：", "quān",
           "表示环形或围拢时读 quān（圆圈）；表示养家畜的棚栏时读 juàn（羊圈）。",
           options=["juàn", "quān", "juān", "quǎn"], correct_index=1),
        _q("g3-c11-4", "G3-C1-1", "basic_choice", "medium",
           "下列加点字读音完全正确的一组是：", "背诵(bèi)  答应(dā)",
           "“背诵”读 bèi（背着书包读 bēi）；“答应”读 dā。",
           options=["背诵(bēi)  答应(dá)", "背诵(bèi)  答应(dā)", "处罚(chù)  几乎(jī)", "稍息(shāo)  骨碌(gǔ)"],
           correct_index=1),
        _hanzi_tile_q("g3-c11-5", "G3-C1-1", "medium", "放假", "fàng jià", ["收", "暇"],
                      "“放假”的“假”是单人旁，读四声 jià。", seed=301),
        _q("g3-c11-6", "G3-C1-1", "dictation_spell", "hard",
           "听录音或看拼音「miǎn qiǎng」，点选字块或输入正确词语：", "勉强",
           "“勉强”中“强”读三声 qiǎng，注意“勉”字写法。",
           hint="2 个汉字", audio_text="勉强", distractors=["免", "强", "力", "壁"]),
    ]

    # G3-C1-2 偏旁部首与形近字辨析
    bank["G3-C1-2"] = [
        _q("g3-c12-1", "G3-C1-2", "basic_choice", "basic",
           "“咬、吞、含、叫”这四个字都含有“口”字旁，它们的意思大多与什么有关？", "嘴巴的动作或声音",
           "口字旁的字大多与嘴巴的动作（咬、吞、含）或发出的声音（叫、吵）有关。",
           options=["眼睛看的动作", "嘴巴的动作或声音", "手部的动作", "金属器皿"], correct_index=1),
        _hanzi_tile_q("g3-c12-2", "G3-C1-2", "basic", "荒野", "huāng yě", ["慌", "墅"],
                      "“荒野”指荒凉的野外，“荒”是草字头，不要加竖心旁写成“慌”。", seed=302),
        _q("g3-c12-3", "G3-C1-2", "basic_choice", "medium",
           "“蜜蜂”和“山峰”中的两个“fēng”字，下面说法正确的是：", "“蜂”是虫字旁与昆虫有关，“峰”是山字旁与高耸的山有关",
           "形声字形旁表义：“虫”旁表昆虫，“山”旁表山岳。",
           options=["两个字可以随便互换", "“蜂”是虫字旁与昆虫有关，“峰”是山字旁与高耸的山有关", "“蜜峰”和“山蜂”才对", "两个字都是提手旁"],
           correct_index=1),
        _hanzi_tile_q("g3-c12-4", "G3-C1-2", "medium", "合拢", "hé lǒng", ["拿", "笼"],
                      "“合拢”指合到一起，“拢”是提手旁，不要写成竹字头的“笼”。", seed=303),
        _q("g3-c12-5", "G3-C1-2", "basic_choice", "hard",
           "下列词语中没有错别字的一项是：", "穿戴  互相  准备",
           "“穿戴”（不是带）、“互相”、“准备”（不是准奋）全部书写正确。",
           options=["穿带  互相  准备", "穿戴  互相  准备", "穿戴  户相  准奋", "穿带  互相  准奋"], correct_index=1),
        _q("g3-c12-6", "G3-C1-2", "dictation_spell", "hard",
           "听录音并结合拼音「fēn fù」，拼写出两个字都带“口”字旁的词语：", "吩咐",
           "“吩咐”两字都带口字旁，表示口头嘱咐。",
           hint="2 个汉字，都带口字旁", audio_text="吩咐", distractors=["份", "付", "吹", "呼"]),
    ]

    # G3-C1-3 ABB/AABB与四字词语积累
    bank["G3-C1-3"] = [
        _q("g3-c13-1", "G3-C1-3", "basic_choice", "basic",
           "下列词语中属于 ABB 式描写颜色的是：", "金灿灿",
           "“金灿灿”是 ABB 式色彩词；“干干净净”是 AABB 式，“七上八下”含数字。",
           options=["干干净净", "金灿灿", "七上八下", "百发百中"], correct_index=1),
        _q("g3-c13-2", "G3-C1-3", "basic_choice", "basic",
           "“提心吊胆、面红耳赤、手忙脚乱”这三个成语有什么共同特点？", "都含有身体部位名称",
           "心、胆、面、耳、手、脚都属于人体部位名称。",
           options=["都描写四季景色", "都含有身体部位名称", "都含有动物名称", "都是 AABB 式词语"], correct_index=1),
        _hanzi_tile_q("g3-c13-3", "G3-C1-3", "medium", "五彩缤纷", "wǔ cǎi bīn fēn", ["采", "宾"],
                      "“五彩缤纷”表示颜色繁多而艳丽，注意“彩”和“缤”的偏旁。", seed=304),
        _q("g3-c13-4", "G3-C1-3", "basic_choice", "medium",
           "形容秋天天空晴朗高远，最恰当的四字词语是：", "秋高气爽",
           "“秋高气爽”专用来形容秋季天空明净、气候凉爽宜人。",
           options=["春暖花开", "烈日炎炎", "秋高气爽", "冰天雪地"], correct_index=2),
        _q("g3-c13-5", "G3-C1-3", "basic_choice", "hard",
           "“孩子们____地冲出教室去堆雪人。”横线上最恰当的词语是：", "兴高采烈",
           "去堆雪人心情非常愉快兴奋，用“兴高采烈”最贴切。",
           options=["垂头丧气", "兴高采烈", "提心吊胆", "大吃一惊"], correct_index=1),
        _q("g3-c13-6", "G3-C1-3", "dictation_spell", "hard",
           "听录音并结合拼音「pò bù jí dài」，写出形容心情十分急切的四字词语：", "迫不及待",
           "“迫不及待”指急迫得不能再等待，注意是“及”不是“急”。",
           hint="4 个汉字", audio_text="迫不及待", distractors=["急", "带", "破", "代"]),
    ]

    # G3-C1-4 听写与看拼音写词语
    bank["G3-C1-4"] = [
        _hanzi_tile_q("g3-c14-1", "G3-C1-4", "basic", "早晨", "zǎo chén", ["旱", "辰"],
                      "“早晨”的“晨”上面是日字头，表示太阳升起的清晨。", seed=305),
        _hanzi_tile_q("g3-c14-2", "G3-C1-4", "basic", "跳舞", "tiào wǔ", ["挑", "午"],
                      "“跳舞”的“跳”是足字旁，与双脚跳跃动作有关。", seed=306),
        _hanzi_tile_q("g3-c14-3", "G3-C1-4", "medium", "翠鸟", "cuì niǎo", ["羽", "乌"],
                      "“翠鸟”的“翠”上半部分是羽字不带钩，“鸟”不要少写一点写成“乌”。", seed=307),
        _q("g3-c14-4", "G3-C1-4", "dictation_spell", "medium",
           "听录音并结合拼音「lí míng」，拼写出表示天快亮时的词语：", "黎明",
           "“黎明”指天快要亮或刚亮的时候。",
           hint="2 个汉字", audio_text="黎明", distractors=["梨", "名", "犁", "鸣"]),
        _q("g3-c14-5", "G3-C1-4", "dictation_spell", "hard",
           "看拼音「guān chá」，拼写出表示仔细察看的词语：", "观察",
           "“观察”指仔细察看事物或现象，注意“察”是宝盖头。",
           hint="2 个汉字", distractors=["现", "查", "祭", "看"]),
        _q("g3-c14-6", "G3-C1-4", "dictation_spell", "hard",
           "听录音并结合拼音「ēn huì」，拼写出表示别人给予的好处的词语：", "恩惠",
           "“恩惠”两字下面都是心字底。",
           hint="2 个汉字", audio_text="恩惠", distractors=["思", "慧", "穗", "怀"]),
    ]

    # G3-C2-1 把字句与被字句转换
    bank["G3-C2-1"] = [
        _q("g3-c21-1", "G3-C2-1", "sentence_choice", "basic",
           "把“秋风吹落了树上的黄叶”改为“把”字句，正确的一项是：", "秋风把树上的黄叶吹落了。",
           "“把”字句结构：动作发出者（秋风）+ 把 + 受动作影响的事物（树上的黄叶）+ 怎样了（吹落了）。",
           options=["树上的黄叶把秋风吹落了。", "秋风把树上的黄叶吹落了。", "秋风被树上的黄叶吹落了。", "树上的黄叶吹落了秋风。"],
           correct_index=1),
        _q("g3-c21-2", "G3-C2-1", "sentence_choice", "basic",
           "把“小猫把桌上的鱼骨头吃光了”改为“被”字句，正确的一项是：", "桌上的鱼骨头被小猫吃光了。",
           "“被”字句把受事者“桌上的鱼骨头”放到句首，加上“被小猫吃光了”。",
           options=["小猫被桌上的鱼骨头吃光了。", "桌上的鱼骨头被小猫吃光了。", "桌上的鱼骨头把小猫吃光了。", "小猫吃光了被桌上的鱼骨头。"],
           correct_index=1),
        _q("g3-c21-3", "G3-C2-1", "sentence_choice", "medium",
           "把“大雨淋湿了少先队员的衣裳”改为“被”字句，正确的是：", "少先队员的衣裳被大雨淋湿了。",
           "衣裳是承受“淋湿”的对象，放在“被”字前面。",
           options=["大雨被少先队员的衣裳淋湿了。", "少先队员的衣裳被大雨淋湿了。", "大雨把少先队员的衣裳被淋湿了。", "少先队员的衣裳把大雨淋湿了。"],
           correct_index=1),
        _q("g3-c21-4", "G3-C2-1", "sentence_choice", "medium",
           "“蜘蛛织好了一张又大又漂亮的网”改为“把”字句，正确的是：", "蜘蛛把一张又大又漂亮的网织好了。",
           "施事者“蜘蛛”在前，受事者“一张又大又漂亮的网”紧跟在“把”后。",
           options=["一张又大又漂亮的网把蜘蛛织好了。", "蜘蛛把一张又大又漂亮的网织好了。", "蜘蛛被一张又大又漂亮的网织好了。", "蜘蛛织好了把一张又大又漂亮的网。"],
           correct_index=1),
        _q("g3-c21-5", "G3-C2-1", "error_spot", "hard",
           "找出下面句式转换中的错误：「阳光把清晨的薄雾被驱散了。」", "“把”和“被”同时混用，应删去“被”",
           "同一句中不能把“把”和“被”混在一起修饰同一动作，删去“被”即可。",
           options=["没有主语", "“把”和“被”同时混用，应删去“被”", "缺少标点符号", "“驱散”用词不当"], correct_index=1),
        _q("g3-c21-6", "G3-C2-1", "sentence_choice", "hard",
           "下列哪一组“把”字句和“被”字句的意思完全一致？", "春风把柳枝吹绿了。 / 柳枝被春风吹绿了。",
           "两句都准确表达了“春风吹绿柳枝”的原意，施事者与受事者关系清晰。",
           options=["春风把柳枝吹绿了。 / 春风被柳枝吹绿了。", "春风把柳枝吹绿了。 / 柳枝被春风吹绿了。", "小鸟把虫子捉住了。 / 小鸟被虫子捉住了。", "洪水把小桥冲垮了。 / 洪水被小桥冲垮了。"],
           correct_index=1),
    ]

    # G3-C2-2 比喻句与拟人句识别
    bank["G3-C2-2"] = [
        _q("g3-c22-1", "G3-C2-2", "sentence_choice", "basic",
           "“水泥道上铺满了金黄的梧桐树叶，像一柄柄金色的小巴掌。”这句话运用的修辞手法是：", "比喻",
           "把“梧桐树叶”比作“金色的小巴掌”，抓住了形状与颜色的相似点，是比喻句。",
           options=["比喻", "拟人", "排比", "反问"], correct_index=0),
        _q("g3-c22-2", "G3-C2-2", "sentence_choice", "basic",
           "“湿润的东风走过荒野，在竹林中吹着口笛。”这句话运用的修辞手法是：", "拟人",
           "把“东风”当作人来写，赋予它“走过荒野”“吹着口笛”的人类动作，是拟人句。",
           options=["比喻", "拟人", "夸张", "设问"], correct_index=1),
        _q("g3-c22-3", "G3-C2-2", "sentence_choice", "medium",
           "注意！含有“像”字的句子不一定是比喻句。下面哪一句是真正的比喻句？", "天上的朵朵白云像一群洁白的小绵羊。",
           "白云和小绵羊是不同类事物且形状相似，是比喻；“他长得像爸爸”是同类比较，不是比喻。",
           options=["他长得真像他的爸爸。", "天上的朵朵白云像一群洁白的小绵羊。", "看这乌云密布的样子，好像要下雨了。", "我好像在哪儿见过这本书。"],
           correct_index=1),
        _q("g3-c22-4", "G3-C2-2", "sentence_choice", "medium",
           "下列句子中，运用了拟人修辞手法的一项是：", "牵牛花吹起了紫色的小喇叭，向早起的人们问好。",
           "“吹喇叭”“向人们问好”赋予了牵牛花人的行为，生动有趣。",
           options=["牵牛花开出了紫色的花朵。", "牵牛花吹起了紫色的小喇叭，向早起的人们问好。", "这朵牵牛花真好看呀！", "院子里的牵牛花每天早上都会开放。"],
           correct_index=1),
        _q("g3-c22-5", "G3-C2-2", "sentence_choice", "hard",
           "“秋天的雨，是一把轻轻打开秋天大门的钥匙。”这句话中，本体和喻体分别是：", "本体是“秋天的雨”，喻体是“钥匙”",
           "把“秋天的雨”（本体）比作“打开秋天大门的钥匙”（喻体）。",
           options=["本体是“钥匙”，喻体是“大门”", "本体是“秋天的雨”，喻体是“钥匙”", "本体是“秋天”，喻体是“雨”", "没有本体和喻体"],
           correct_index=1),
        _q("g3-c22-6", "G3-C2-2", "sentence_choice", "hard",
           "要想把“小溪向前流”改写成生动的拟人句，下面最好的一句是：", "清澈的小溪唱着欢快的歌儿，一路蹦蹦跳跳地跑向大海。",
           "赋予小溪“唱歌”“蹦蹦跳跳地跑”的人类动作与情态，画面鲜活。",
           options=["清澈的小溪流得非常非常快。", "清澈的小溪像一条长长的丝带。", "清澈的小溪唱着欢快的歌儿，一路蹦蹦跳跳地跑向大海。", "小溪里的水日夜不停地往前流。"],
           correct_index=2),
    ]

    # G3-C2-3 提示语位置与标点符号
    bank["G3-C2-3"] = [
        _q("g3-c23-1", "G3-C2-3", "sentence_choice", "basic",
           "提示语在前面时，“蚂蚁队长说____‘照样要受处罚！’”横线上应填什么标点？", "冒号（：）",
           "提示语在说话内容前面时，“说”字后面用冒号引出引号内的话。",
           options=["逗号（，）", "句号（。）", "冒号（：）", "问号（？）"], correct_index=2),
        _q("g3-c23-2", "G3-C2-3", "sentence_choice", "basic",
           "提示语在后面时，“‘救命啊！’红头拼命地叫了起来____”句末和“叫了起来”前面分别用什么标点？", "直接接文字，句末用句号",
           "提示语在后面时，引号内话语结束后直接写提示语，提示语末尾用句号。",
           options=["先加冒号，句末用问号", "直接接文字，句末用句号", "先加句号，句末用冒号", "不需要引号"], correct_index=1),
        _q("g3-c23-3", "G3-C2-3", "sentence_choice", "medium",
           "提示语在中间时，“‘不要紧，’小公鸡说道____‘第一次能这样就很不错了。’”横线上应填什么标点？", "逗号（，）",
           "提示语夹在两段话中间时，“说道”后面一定要用逗号，不能用冒号或句号。",
           options=["冒号（：）", "句号（。）", "逗号（，）", "感叹号（！）"], correct_index=2),
        _q("g3-c23-4", "G3-C2-3", "sentence_choice", "medium",
           "下列句子中标点符号使用完全正确的一项是：", "“真是太好啦！”小男孩高兴地跳了起来。",
           "提示语在后，感叹句放引号内，提示语末尾用句号。",
           options=["“真是太好啦！”小男孩高兴地跳了起来：", "“真是太好啦！”小男孩高兴地跳了起来。", "小男孩高兴地说，“真是太好啦！”", "“真是太好啦，”小男孩说：“我们出发吧！”"],
           correct_index=1),
        _q("g3-c23-5", "G3-C2-3", "error_spot", "hard",
           "找出下面句子标点符号的错误之处：「“快看！”小丽指着天空喊道：“天边出现了一道彩虹！”」", "提示语“喊道”在中间，后面的冒号应改为逗号",
           "前后都是小丽说的话，提示语在中间时，“喊道”后面必须用逗号。",
           options=["感叹号应改为句号", "提示语“喊道”在中间，后面的冒号应改为逗号", "不应该用双引号", "“快看”后面不能用感叹号"],
           correct_index=1),
        _q("g3-c23-6", "G3-C2-3", "sentence_choice", "hard",
           "妈妈温柔地问我：“今天在学校里有什么好玩的事吗____”横线上应填：", "？（问号放在右引号里面）",
           "直接引用的完整疑问句，问号要放在右双引号的里面。",
           options=["。”", "？（问号放在右引号里面）", "”？", "，"], correct_index=1),
    ]

    # G3-C2-4 常见简单病句诊断
    bank["G3-C2-4"] = [
        _q("g3-c24-1", "G3-C2-4", "error_spot", "basic",
           "找出下面病句的病因：「菜园里种着西红柿、黄瓜、西瓜和蔬菜。」", "分类不当（西瓜是水果，且蔬菜包含了前两项）",
           "西红柿、黄瓜本身就是蔬菜，西瓜是水果，不能并列说“和蔬菜”。",
           options=["缺少主语", "分类不当（西瓜是水果，且蔬菜包含了前两项）", "用词重复", "语序颠倒"], correct_index=1),
        _q("g3-c24-2", "G3-C2-4", "error_spot", "basic",
           "找出下面病句的病因：「我穿上一件新毛衣和一顶小红帽。」", "搭配不当（“穿上”不能搭配“小红帽”）",
           "毛衣可以“穿上”，但帽子应该用“戴上”，应改为“穿上一件新毛衣，戴上一顶小红帽”。",
           options=["前后矛盾", "搭配不当（“穿上”不能搭配“小红帽”）", "语义重复", "没有病句"], correct_index=1),
        _q("g3-c24-3", "G3-C2-4", "error_spot", "medium",
           "找出下面病句的病因：「看了这部有趣的童话电影，使我哈哈大笑。」", "成分残缺（缺少主语，应删去“使”）",
           "“看了……，使我……”缺主语，删去“使”字就通顺了。",
           options=["成分残缺（缺少主语，应删去“使”）", "分类不当", "前后矛盾", "标点错误"], correct_index=0),
        _q("g3-c24-4", "G3-C2-4", "error_spot", "medium",
           "找出下面病句的病因：「广场上飘扬着五颜六色的红旗。」", "前后矛盾（“五颜六色”与“红旗”矛盾）",
           "红旗只有红色，不能用“五颜六色”修饰，可删去“五颜六色的”或把“红旗”改为“彩旗”。",
           options=["缺少动作", "前后矛盾（“五颜六色”与“红旗”矛盾）", "语序颠倒", "用词重复"], correct_index=1),
        _q("g3-c24-5", "G3-C2-4", "sentence_choice", "hard",
           "下列句子中没有语病的一项是：", "星期天，我和爸爸一起去公园观察秋天的落叶。",
           "A 重复（忍不住/不禁）；B 矛盾（几乎/全部）；D 搭配不当（听到……笑容）。",
           options=["我忍不住不禁笑了起来。", "全班同学几乎全部都交了作业。", "星期天，我和爸爸一起去公园观察秋天的落叶。", "我们在教室里听到了老师亲切的笑容。"],
           correct_index=2),
        _q("g3-c24-6", "G3-C2-4", "error_spot", "hard",
           "找出下面病句的病因：「语文课上，我们讨论并听取了班长提出的读书建议。」", "语序不当（应该先“听取”再“讨论”）",
           "按照事物发展的先后顺序，必须先“听取”建议，然后才能“讨论”建议。",
           options=["缺少主语", "语序不当（应该先“听取”再“讨论”）", "分类不当", "前后矛盾"], correct_index=1),
    ]

    # G3-C3-1 三年级写景名篇（《望天门山》《山行》《饮湖上初晴后雨》）
    bank["G3-C3-1"] = [
        _poem_tile_q("g3-c31-1", "G3-C3-1", "basic",
                     "点选字块，补全杜牧《山行》名句：「停车坐爱枫林晚，____。」",
                     "霜叶红于二月花", ["双", "春"],
                     "“霜叶红于二月花”赞美经霜的枫叶比二月的春花还要火红。", seed=331),
        _poem_tile_q("g3-c31-2", "G3-C3-1", "basic",
                     "点选字块，补全李白《望天门山》名句：「两岸青山相对出，____。」",
                     "孤帆一片日边来", ["狐", "船"],
                     "“孤帆一片日边来”写出小船从太阳升起的天边乘风破浪而来的壮阔景象。", seed=332),
        _q("g3-c31-3", "G3-C3-1", "reading_choice", "medium",
           "杜牧《山行》“停车坐爱枫林晚”中的“坐”字，正确的意思是：", "因为",
           "古诗中“坐”常作“因为”讲，意为因为喜爱傍晚的枫林景色而停下车来。",
           options=["坐在地上", "因为", "座位", "乘坐马车"], correct_index=1),
        _q("g3-c31-4", "G3-C3-1", "reading_choice", "medium",
           "苏轼《饮湖上初晴后雨》中，把西湖比作古代美女西施的名句是：", "欲把西湖比西子，淡妆浓抹总相宜。",
           "诗人将晴天和雨天的西湖比作淡妆浓抹皆美的西施（西子）。",
           options=["天门中断楚江开，碧水东流至此回。", "欲把西湖比西子，淡妆浓抹总相宜。", "远上寒山石径斜，白云生处有人家。", "湖光秋月两相和，潭面无风镜未磨。"],
           correct_index=1),
        _q("g3-c31-5", "G3-C3-1", "poem_fill", "hard",
           "精准默写杜牧《山行》后两句中的下句：「停车坐爱枫林晚，________。」（不加标点）",
           "霜叶红于二月花",
           "注意“霜”是雨字头，“于”不要写成“与”。",
           hint="7 个汉字，出自《山行》", distractors=["双", "与", "春", "草"]),
        _q("g3-c31-6", "G3-C3-1", "poem_fill", "hard",
           "精准默写苏轼《饮湖上初晴后雨》首句：「水光潋滟晴方好，________。」",
           "山色空蒙雨亦奇",
           "晴天水波闪动很美，雨天山色迷茫也别有奇趣。",
           hint="7 个汉字，出自《饮湖上初晴后雨》", distractors=["空", "奇", "青", "云"]),
    ]

    # G3-C3-2 传统节日与儿童古诗（《元日》《九月九日忆山东兄弟》《所见》）
    bank["G3-C3-2"] = [
        _poem_tile_q("g3-c32-1", "G3-C3-2", "basic",
                     "点选字块，补全王维《九月九日忆山东兄弟》名句：「独在异乡为异客，____。」",
                     "每逢佳节倍思亲", ["梅", "陪"],
                     "每遇到美好的节日就加倍思念家乡的亲人。", seed=333),
        _poem_tile_q("g3-c32-2", "G3-C3-2", "basic",
                     "点选字块，补全袁枚《所见》名句：「意欲捕鸣蝉，____。」",
                     "忽然闭口立", ["必", "粒"],
                     "牧童想要捕捉树上鸣叫的知了，忽然停下歌声闭上嘴巴静静站立。", seed=334),
        _q("g3-c32-3", "G3-C3-2", "reading_choice", "medium",
           "王安石《元日》“爆竹声中一岁除，春风送暖入屠苏”描写的是哪个传统节日？", "春节（农历正月初一）",
           "“元日”即农历正月初一春节，诗中写了放爆竹、喝屠苏酒、换桃符的迎新习俗。",
           options=["中秋节", "端午节", "春节（农历正月初一）", "重阳节"], correct_index=2),
        _q("g3-c32-4", "G3-C3-2", "reading_choice", "medium",
           "《九月九日忆山东兄弟》中“遥知兄弟登高处，遍插茱萸少一人”描写的重阳节习俗是：", "登高远眺、插戴茱萸",
           "农历九月初九重阳节，古人有登高、插茱萸的传统习俗。",
           options=["吃月饼、赏明月", "赛龙舟、包粽子", "登高远眺、插戴茱萸", "贴春联、守岁"], correct_index=2),
        _q("g3-c32-5", "G3-C3-2", "poem_fill", "hard",
           "精准默写王维《九月九日忆山东兄弟》第二句：「独在异乡为异客，________。」",
           "每逢佳节倍思亲",
           "“倍”是单人旁，表示“加倍”。",
           hint="7 个汉字", distractors=["陪", "培", "佳", "家"]),
        _q("g3-c32-6", "G3-C3-2", "poem_fill", "hard",
           "精准默写王安石《元日》末句：「千门万户曈曈日，________。」",
           "总把新桃换旧符",
           "家家户户用新桃符换下旧桃符，除旧迎新。",
           hint="7 个汉字，出自《元日》", distractors=["逃", "付", "春", "福"]),
    ]

    # G3-C3-3 启蒙小古文（《司马光》《守株待兔》）
    bank["G3-C3-3"] = [
        _q("g3-c33-1", "G3-C3-3", "reading_choice", "basic",
           "《司马光》中“群儿戏于庭，一儿登瓮，足跌没水中”的“庭”和“瓮”分别指什么？", "庭院；口小肚大的陶器大缸",
           "“庭”指庭院；“瓮”是指口小肚大的陶器水缸。",
           options=["客厅；小碗", "庭院；口小肚大的陶器大缸", "草地；池塘", "操场；水桶"], correct_index=1),
        _q("g3-c33-2", "G3-C3-3", "reading_choice", "basic",
           "“众皆弃去，光持石击瓮破之”中，“皆”和“持”的意思分别是：", "全、都；拿起",
           "其他孩子全都吓得跑开了（众皆弃去），司马光拿起石头砸破水缸（持石击瓮）。",
           options=["一个；扔掉", "全、都；拿起", "有时；放下", "一起；看着"], correct_index=1),
        _q("g3-c33-3", "G3-C3-3", "reading_choice", "medium",
           "《守株待兔》中“兔走触株，折颈而死”的“走”在古文中的意思是：", "跑（狂奔）",
           "古汉语中“走”意为“跑”，不是现代汉语的“步行”。",
           options=["慢慢散步", "跑（狂奔）", "跳高", "睡觉"], correct_index=1),
        _q("g3-c33-4", "G3-C3-3", "reading_choice", "medium",
           "“因释其耒而守株，冀复得兔”中，农夫为什么会被宋国人笑话？", "他把偶然撞死兔子的巧合当成天天都会发生的事，放弃耕作只想不劳而获",
           "《守株待兔》告诫人们不要心存侥幸、妄想不劳而获。",
           options=["他跑得没有兔子快", "他把偶然撞死兔子的巧合当成天天都会发生的事，放弃耕作只想不劳而获", "他不认识兔子的品种", "他的农具太旧了"],
           correct_index=1),
        _poem_tile_q("g3-c33-5", "G3-C3-3", "hard",
                     "点选字块，补全《司马光》名句：「光持石击瓮破之，水迸，____。」",
                     "儿得活", ["女", "死"],
                     "水一下子涌出来，掉进缸里的小孩得以获救。", seed=335),
        _q("g3-c33-6", "G3-C3-3", "poem_fill", "hard",
           "精准默写《守株待兔》中写兔子撞树桩的八字古文：「________，折颈而死。」",
           "兔走触株",
           "“兔走触株”意为野兔奔跑时撞在树桩上。",
           hint="4 个汉字", distractors=["免", "珠", "虫", "足"]),
    ]

    # G3-C3-4 气象谚语与格言积累
    bank["G3-C3-4"] = [
        _poem_tile_q("g3-c34-1", "G3-C3-4", "basic",
                     "点选字块补全团结格言：「二人同心，____。」",
                     "其利断金", ["旗", "力"],
                     "“二人同心，其利断金”比喻只要大家齐心协力，就能发挥巨大的力量。", seed=336),
        _q("g3-c34-2", "G3-C3-4", "reading_choice", "basic",
           "“灯不拨不亮，理不辩不明”告诉我们的道理是：", "道理要经过讨论辨析，才会越来越清楚明白",
           "油灯不拨灯芯就不亮，道理不经过探讨辩论就不会透彻明白。",
           options=["每天晚上都要点油灯", "道理要经过讨论辨析，才会越来越清楚明白", "不要和同学讨论问题", "油灯比电灯更亮"],
           correct_index=1),
        _q("g3-c34-3", "G3-C3-4", "reading_choice", "medium",
           "“三个臭皮匠，顶个诸葛亮”与下面哪句谚语的意思最相近？", "人心齐，泰山移。",
           "两句都强调团结协作、集思广益的巨大力量。",
           options=["人心齐，泰山移。", "盛年不重来，一日难再晨。", "敏而好学，不耻下问。", "由俭入奢易，由奢入俭难。"],
           correct_index=0),
        _q("g3-c34-4", "G3-C3-4", "reading_choice", "medium",
           "“爱人若爱其身”出自《墨子》，意思是：", "关心爱护别人就像爱护自己一样",
           "倡导仁爱互助、推己及人的美德。",
           options=["只爱自己不爱别人", "关心爱护别人就像爱护自己一样", "每天都要锻炼身体", "爱护自己的衣服"],
           correct_index=1),
        _q("g3-c34-5", "G3-C3-4", "poem_fill", "hard",
           "精准默写团结谚语下句：「人心齐，________。」",
           "泰山移",
           "只要大家齐心协力，连泰山都能移走。",
           hint="3 个汉字", distractors=["太", "多", "动", "走"]),
        _q("g3-c34-6", "G3-C3-4", "poem_fill", "hard",
           "精准默写关于讲理的八字俗语下句：「有理走遍天下，________。」",
           "无理寸步难行",
           "做事讲道理走到哪里都行得通，不讲道理则寸步难行。",
           hint="6 个汉字", distractors=["里", "村", "步", "形"]),
    ]

    # G3-C4-1 找中心句与概括段意
    p_g3_center = (
        "西沙群岛也是鸟的天下。岛上有一片片茂密的树林，树林里栖息着各种海鸟。"
        "遍地都是鸟蛋。树下堆积着一层厚厚的鸟粪，这是非常宝贵的肥料。"
    )
    bank["G3-C4-1"] = [
        _q("g3-c41-1", "G3-C4-1", "reading_choice", "basic",
           "阅读短文，这段话是围绕哪一句话来写的（中心句）？", "西沙群岛也是鸟的天下。",
           "第一句总领全段，后面写树林多、海鸟多、鸟蛋多、鸟粪多，都围绕“鸟的天下”展开。",
           options=["岛上有一片片茂密的树林。", "西沙群岛也是鸟的天下。", "遍地都是鸟蛋。", "这是非常宝贵的肥料。"],
           correct_index=1, passage=p_g3_center),
        _q("g3-c41-2", "G3-C4-1", "reading_choice", "basic",
           "作者是从哪几个方面把“西沙群岛也是鸟的天下”写具体的？", "树林茂密海鸟多、遍地是鸟蛋、树下鸟粪厚",
           "分述句依次写了树林与海鸟、鸟蛋、鸟粪三个具体画面。",
           options=["海水五光十色、珊瑚好看", "树林茂密海鸟多、遍地是鸟蛋、树下鸟粪厚", "鱼成群结队、海龟有趣", "沙滩上有许多贝壳"],
           correct_index=1, passage=p_g3_center),
        _q("g3-c41-3", "G3-C4-1", "reading_choice", "medium",
           "段落的中心句最常出现在段落的什么位置？", "段首（第一句），有时也在段尾或段中",
           "三年级常见的总分结构段落，中心句通常在段首第一句，起到总领全段的作用。",
           options=["只能在正中间第三个字", "段首（第一句），有时也在段尾或段中", "一定不在段落里", "只能是最后一个词"],
           correct_index=1),
        _q("g3-c41-4", "G3-C4-1", "reading_choice", "medium",
           "找到段落的中心句对我们阅读有什么帮助？", "能帮我们快速抓住这段话的主要意思",
           "中心句概括了全段的核心意思，抓中心句是概括段意最快最准的方法。",
           options=["可以不用读课文了", "能帮我们快速抓住这段话的主要意思", "能帮我们查生字读音", "能计算段落有多少个字"],
           correct_index=1),
        _q("g3-c41-5", "G3-C4-1", "reading_short", "hard",
           "【阅读简答】读一读短文，为什么说西沙群岛是“鸟的天下”？请结合文中内容用 1～2 句话回答。",
           "因为岛上树林茂密，栖息着各种海鸟，地上遍地都是鸟蛋，树下还堆积着厚厚的鸟粪，说明鸟非常多。",
           "答题思路：从文中找出树多鸟多、鸟蛋多、鸟粪多这三个依据来回答。",
           passage=p_g3_center,
           rubric_keywords=[["树林", "海鸟", "栖息"], ["鸟蛋", "遍地"], ["鸟粪", "厚", "多"]],
           min_chars=12,
           sample_answer="因为岛上树林里栖息着各种海鸟，遍地都是鸟蛋，树下还堆着厚厚的鸟粪，处处都能看出海鸟非常多。",
           scaffolds=[
               "开头可用：因为西沙群岛上不仅有……，还有……",
               "关键词提示：各种海鸟、遍地鸟蛋、厚厚的鸟粪",
               "结尾点题：所以说那里真是鸟的天下。",
           ]),
        _q("g3-c41-6", "G3-C4-1", "reading_choice", "hard",
           "如果我们要围绕“操场上真热闹呀！”写一段话，下面哪个画面不适合写进去？", "图书馆里静悄悄的，大家都在安静看书。",
           "围绕“操场热闹”只能写操场上的欢快运动画面，不能写图书馆安静看书。",
           options=["同学们有的在跳绳，有的在踢毽子。", "跑道上运动员们正你追我赶地赛跑。", "图书馆里静悄悄的，大家都在安静看书。", "加油声和欢笑声在操场上空回荡。"],
           correct_index=2),
    ]

    # G3-C4-2 童话寓言阅读与道理体会
    p_g3_fable = (
        "小壁虎去借尾巴。它先爬到小河边向小鱼姐姐借，小鱼说：“不行啊，我要用尾巴拨水呢。”"
        "它又爬到大树上向老牛伯伯借，老牛说：“不行啊，我要用尾巴赶蝇子呢。”"
        "它再向燕子阿姨借，燕子说：“不行啊，我要用尾巴掌握方向呢。”"
        "小壁虎难过地爬回家找妈妈，妈妈笑着说：“傻孩子，你看，你的新尾巴已经长出来啦！”"
    )
    bank["G3-C4-2"] = [
        _q("g3-c42-1", "G3-C4-2", "reading_choice", "basic",
           "小壁虎先后向哪三位朋友借尾巴？", "小鱼、老牛、燕子",
           "按短文顺序依次是小鱼姐姐、老牛伯伯、燕子阿姨。",
           options=["小猫、小狗、燕子", "小鱼、老牛、燕子", "青蛙、松鼠、老牛", "小鱼、公鸡、喜鹊"],
           correct_index=1, passage=p_g3_fable),
        _q("g3-c42-2", "G3-C4-2", "reading_choice", "basic",
           "燕子阿姨的尾巴有什么重要用处？", "飞行时掌握方向",
           "原文燕子说：“我要用尾巴掌握方向呢。”",
           options=["在水里拨水", "赶走身上的蝇子", "飞行时掌握方向", "当降落伞用"],
           correct_index=2, passage=p_g3_fable),
        _q("g3-c42-3", "G3-C4-2", "reading_choice", "medium",
           "小壁虎最后为什么不用借别人的尾巴了？", "因为壁虎的尾巴有再生能力，自己长出了一条新尾巴",
           "壁虎断尾逃生后能自己重新长出新尾巴。",
           options=["燕子把尾巴借给它了", "因为壁虎的尾巴有再生能力，自己长出了一条新尾巴", "它决定以后不要尾巴了", "老牛送了它一条尾巴"],
           correct_index=1, passage=p_g3_fable),
        _q("g3-c42-4", "G3-C4-2", "reading_choice", "medium",
           "这篇知识童话通过小壁虎借尾巴的故事，主要告诉我们什么科学道理？", "不同动物的尾巴各有各的独特用处",
           "小鱼拨水、老牛赶蝇子、燕子掌握方向、壁虎再生，说明动物尾巴各有重要功能。",
           options=["动物们都很小气不肯借东西", "不同动物的尾巴各有各的独特用处", "小壁虎最喜欢在河里游泳", "尾巴没有任何用处"],
           correct_index=1, passage=p_g3_fable),
        _q("g3-c42-5", "G3-C4-2", "reading_short", "hard",
           "【阅读简答】小鱼、老牛和燕子为什么都不把尾巴借给小壁虎？请结合短文说说它们的尾巴分别有什么作用。",
           "因为它们的尾巴都有重要用处：小鱼要用尾巴拨水，老牛要用尾巴赶蝇子，燕子要用尾巴掌握方向。",
           "答题思路：分别写出小鱼（拨水）、老牛（赶蝇子）、燕子（掌握方向）的尾巴功能。",
           passage=p_g3_fable,
           rubric_keywords=[["小鱼", "拨水"], ["老牛", "赶蝇", "蝇子"], ["燕子", "方向"]],
           min_chars=12,
           sample_answer="因为它们的尾巴各有各的用处：小鱼要用尾巴拨水，老牛要用尾巴赶蝇子，燕子要用尾巴掌握方向。",
           scaffolds=[
               "开头可用：因为它们的尾巴都有重要的用处：",
               "要点提示：小鱼拨水、老牛赶蝇子、燕子掌握方向",
               "句式参考：小鱼用尾巴……，老牛用尾巴……，燕子用尾巴……",
           ]),
        _q("g3-c42-6", "G3-C4-2", "reading_choice", "hard",
           "阅读童话故事时，我们不仅能感受到奇特的想象，还能：", "从故事中体会做人的道理或有趣的科学知识",
           "童话既充满奇妙想象，又蕴含真善美的道理或科普知识。",
           options=["把童话当成真实的新闻报道", "从故事中体会做人的道理或有趣的科学知识", "只看插图不读文字", "跳过结局不看"],
           correct_index=1),
    ]

    # G3-C4-3 自然景物与动植物观察阅读
    p_g3_nature = (
        "原来，蒲公英的花就像我们的手掌，可以张开、合上。"
        "花朵张开时，花瓣是金色的，草地也是金色的；花朵合拢时，金色的花瓣被包住了，草地就变成绿色的了。"
    )
    bank["G3-C4-3"] = [
        _q("g3-c43-1", "G3-C4-3", "reading_choice", "basic",
           "作者在短文中把蒲公英的花比作了什么？", "我们的手掌（可以张开、合上）",
           "第一句明确写道：“蒲公英的花就像我们的手掌，可以张开、合上。”",
           options=["金色的小太阳", "我们的手掌（可以张开、合上）", "绿色的小伞", "天上的星星"],
           correct_index=1, passage=p_g3_nature),
        _q("g3-c43-2", "G3-C4-3", "reading_choice", "basic",
           "当蒲公英的花朵合拢时，草地会变成什么颜色？", "绿色",
           "花朵合拢时，金色的花瓣被绿色的花萼包住了，草地就变成绿色的了。",
           options=["金色", "绿色", "红色", "白色"],
           correct_index=1, passage=p_g3_nature),
        _q("g3-c43-3", "G3-C4-3", "reading_choice", "medium",
           "小作者为什么能发现草地变色的秘密？", "因为他留心观察，而且在不同时间进行了细致连续的观察",
           "只有早、中、晚连续细致观察，才能发现花朵张开与合拢导致草地变色的奥秘。",
           options=["因为他随便猜了一下", "因为他留心观察，而且在不同时间进行了细致连续的观察", "因为别人直接告诉了他", "因为他把花全部摘回家了"],
           correct_index=1, passage=p_g3_nature),
        _q("g3-c43-4", "G3-C4-3", "reading_choice", "medium",
           "观察一种小动物或植物时，除了用眼睛看颜色和形状，还可以：", "用耳朵听声音、用鼻子闻气味、用手轻轻触摸感受",
           "调动视觉、听觉、嗅觉、触觉等多种感官，观察才会更全面生动。",
           options=["只看一眼就走开", "用耳朵听声音、用鼻子闻气味、用手轻轻触摸感受", "什么都不记录", "只抄字典上的解释"],
           correct_index=1),
        _q("g3-c43-5", "G3-C4-3", "reading_short", "hard",
           "【阅读简答】为什么草地一会儿是金色的，一会儿又变成绿色的？请根据短文内容简要回答。",
           "因为蒲公英的花朵张开时露出金色花瓣，草地就是金色的；花朵合拢时金色花瓣被包住，草地就变成绿色的了。",
           "答题思路：分别说明“花朵张开时”和“花朵合拢时”花瓣的状态与草地颜色的变化。",
           passage=p_g3_nature,
           rubric_keywords=[["张开", "金色"], ["合拢", "合上", "包住", "绿色"]],
           min_chars=12,
           sample_answer="因为蒲公英的花朵张开时露出金色花瓣，草地是金色的；花朵合拢时金色花瓣被包住了，草地就变成绿色的了。",
           scaffolds=[
               "句式支架：当蒲公英花朵张开时……；当花朵合拢时……",
               "关键词提示：张开、金色花瓣、合拢、被包住、绿色",
               "观察小结：蒲公英就像我们的手掌一样会开合。",
           ]),
        _q("g3-c43-6", "G3-C4-3", "reading_choice", "hard",
           "读了这段话，我们能体会到小作者对大自然怀着怎样的感情？", "喜爱大自然、乐于观察探索自然奥秘",
           "细致有趣的比喻和观察记录字里行间洋溢着对大自然的喜爱。",
           options=["讨厌草地", "喜爱大自然、乐于观察探索自然奥秘", "觉得蒲公英很无聊", "害怕去草地玩"],
           correct_index=1, passage=p_g3_nature),
    ]

    # G3-C4-4 观察写话与50字微段落表达
    bank["G3-C4-4"] = [
        _q("g3-c44-1", "G3-C4-4", "reading_choice", "basic",
           "三年级写观察日记或小动物微段落时，怎样才能让句子更生动？", "抓住小动物的外形特点和有趣动作，用上比喻或拟人",
           "外形+动作+恰当的比喻拟人，能让小动物活灵活现。",
           options=["只写一句“它很好看”就结束", "抓住小动物的外形特点和有趣动作，用上比喻或拟人", "写满一整页生字拼音", "不写标点符号"],
           correct_index=1),
        _q("g3-c44-2", "G3-C4-4", "reading_choice", "basic",
           "把“小兔子很可爱”写具体，下面哪一句最好？", "小兔子浑身雪白，像一团软绵绵的棉花糖，红宝石似的大眼睛一眨一眨的。",
           "既写出了皮毛雪白（比作棉花糖），又写出了红眼睛（比作红宝石），画面感十足。",
           options=["小兔子真的非常非常可爱。", "我家有一只很可爱的小兔子。", "小兔子浑身雪白，像一团软绵绵的棉花糖，红宝石似的大眼睛一眨一眨的。", "小兔子有四条腿和两只耳朵。"],
           correct_index=2),
        _q("g3-c44-3", "G3-C4-4", "reading_choice", "medium",
           "写《秋天的果园》微段落时，如果开头写“秋天的果园真是一个丰收的乐园！”，后面应该接着写什么？", "分别写红彤彤的苹果、黄澄澄的梨和紫玛瑙似的葡萄",
           "围绕总起句“丰收的乐园”，分写各种成熟水果的色彩与形态。",
           options=["写冬天怎么堆雪人", "分别写红彤彤的苹果、黄澄澄的梨和紫玛瑙似的葡萄", "写自己在教室里做数学题", "写春天的燕子飞回来了"],
           correct_index=1),
        _q("g3-c44-4", "G3-C4-4", "reading_choice", "medium",
           "写童话小故事时，为了让故事完整，应该包含哪些基本要素？", "时间地点、童话角色、发生了什么有趣的事以及结果",
           "把角色、起因、经过、结果交代清楚，童话小故事才完整。",
           options=["只要写三个角色的名字", "时间地点、童话角色、发生了什么有趣的事以及结果", "只写一句口号", "不需要有任何动作和对话"],
           correct_index=1),
        _q("g3-c44-5", "G3-C4-4", "micro_writing", "hard",
           "【微段落写话】请仔细观察你喜欢的一种小动物或美丽景物（如小猫、小兔子、秋天的落叶），写一段 40～70 字的小话，试着用上一个比喻句或拟人句。",
           "语句通顺，写出动物或景物的颜色、外形或有趣动作，并用上比喻或拟人。",
           "写话提示：先写它的样子或颜色（像什么），再写它的一个可爱动作。",
           rubric_keywords=[["像", "好似", "仿佛", "如同", "唱", "跳", "笑", "招手"], ["白", "黄", "红", "绿", "金", "圆", "毛", "眼", "叶", "花", "尾", "耳"]],
           min_chars=35,
           sample_answer="我家的小白猫可爱极了！它浑身雪白，像一团会滚动的棉花糖。圆溜溜的眼睛像两颗发亮的绿宝石。每当看到毛线球，它就欢快地扑过去，抱着线球打滚。",
           scaffolds=[
               "开头可用：我最喜欢……，它长着……，像……",
               "好词锦囊：雪白雪白、圆溜溜、金灿灿、翩翩起舞、活蹦乱跳",
               "动作支架：每当……的时候，它就会欢快地……",
           ]),
        _q("g3-c44-6", "G3-C4-4", "micro_writing", "hard",
           "【微段落写话】请围绕中心句「秋天的公园真美呀！」写一段 40～70 字的话，写出 2～3 种秋天的景物（如枫叶、菊花、银杏叶）。",
           "围绕“秋天的公园真美”展开，写出枫叶、菊花或银杏叶的颜色与姿态。",
           "写话提示：用“有的……有的……”或并列句写出秋天的色彩与生机。",
           rubric_keywords=[["秋", "公园", "美"], ["叶", "花", "枫", "菊", "银杏", "树"], ["红", "黄", "金", "五颜六色", "五彩缤纷", "像"]],
           min_chars=35,
           sample_answer="秋天的公园真美呀！金黄的银杏叶像一把把小扇子，扇走了夏天的炎热。火红的枫叶像一枚枚邮票，菊花仙子也穿上了五彩缤纷的衣裳，在秋风里频频点头。",
           scaffolds=[
               "开头可用：秋天的公园真美呀！你看，金黄的银杏叶像……",
               "好词锦囊：五彩缤纷、火红火红、金灿灿、翩翩起舞、频频点头",
               "句式支架：火红的枫叶像……，五颜六色的菊花在秋风里……",
           ]),
    ]

    return bank


def _build_g4_questions() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in CHINESE_G4_NODES}

    # G4-C1-1 多音字语境辨音与易误读字
    bank["G4-C1-1"] = [
        _q("g4-c11-1", "G4-C1-1", "basic_choice", "basic",
           "“薄雾笼罩着江面”与“薄荷糖”中两个“薄”的读音分别是：", "bó / bò",
           "合成词“薄雾、单薄”读 bó；“薄荷”读 bò；单用口语“厚薄”读 báo。",
           options=["báo / bó", "bó / bò", "bò / báo", "bó / bó"], correct_index=1),
        _q("g4-c11-2", "G4-C1-1", "basic_choice", "basic",
           "“家雀儿”中“雀”在口语里的正确读音是：", "qiǎo",
           "“家雀儿”（麻雀的俗称）中“雀”读 qiǎo；在“麻雀、孔雀”中读 què。",
           options=["què", "qiǎo", "qiāo", "qüè"], correct_index=1),
        _q("g4-c11-3", "G4-C1-1", "basic_choice", "medium",
           "“宁可”与“安宁”中“宁”的读音分别是：", "nìng / níng",
           "表示情愿、宁肯时读四声 nìng（宁可、宁愿）；表示平安、平静时读二声 níng（安宁）。",
           options=["níng / nìng", "nìng / níng", "níng / níng", "nǐng / níng"], correct_index=1),
        _q("g4-c11-4", "G4-C1-1", "basic_choice", "medium",
           "下列加点字读音完全正确的一组是：", "角色(jué)  弯曲(qū)",
           "“角色”读 jué（不读 jiǎo）；“弯曲”读 qū（“歌曲”读 qǔ）。",
           options=["角色(jiǎo)  弯曲(qǔ)", "角色(jué)  弯曲(qū)", "露面(lù)  要求(yào)", "扎针(zā)  投降(xiáng)"],
           correct_index=1),
        _hanzi_tile_q("g4-c11-5", "G4-C1-1", "medium", "平衡", "píng héng", ["评", "恒"],
                      "“平衡”注意后鼻音 héng，不要写成“评恒”。", seed=401, audio_text="平衡"),
        _q("g4-c11-6", "G4-C1-1", "dictation_spell", "hard",
           "听录音并结合拼音「lǐng lüè」，写出正确词语：", "领略",
           "“领略”中“略”是田字旁，注意韵母 üe。",
           hint="2 个汉字", audio_text="领略", distractors=["令", "掠", "路", "格"]),
    ]

    # G4-C1-2 形声字与易错字形辨析
    bank["G4-C1-2"] = [
        _q("g4-c12-1", "G4-C1-2", "basic_choice", "basic",
           "“暮色、幕布、羡慕”三个词中的“mù”，为什么偏旁不同？", "日字底与傍晚时间有关，巾字底与布匹帐篷有关，心字底与心理活动有关",
           "形声字形旁表义：日→日落傍晚（暮），巾→布帛（幕），心(⺗)→心里向往（慕）。",
           options=["只是随便规定的", "日字底与傍晚时间有关，巾字底与布匹帐篷有关，心字底与心理活动有关", "三个字意思完全一样", "三个字都与花草有关"],
           correct_index=1),
        _hanzi_tile_q("g4-c12-2", "G4-C1-2", "basic", "懒惰", "lǎn duò", ["赖", "随"],
                      "“懒惰”两个字都是竖心旁。", seed=402, audio_text="懒惰"),
        _q("g4-c12-3", "G4-C1-2", "basic_choice", "medium",
           "“辩论、分辨、花瓣、辫子”四个词中，与“言语争论”有关的是：", "中间是言字旁的“辩”",
           "中间是“讠”（言）的是“辩论”；中间是刀/点撇的是“分辨”；中间是瓜的是“花瓣”；中间是纟的是“辫子”。",
           options=["中间是瓜的“瓣”", "中间是言字旁的“辩”", "中间是绞丝旁的“辫”", "中间是刀点的“辨”"],
           correct_index=1),
        _hanzi_tile_q("g4-c12-4", "G4-C1-2", "medium", "繁殖", "fán zhí", ["繁", "植"],
                      "“繁殖”的“殖”是歹字旁，不是木字旁“植”。", seed=403, audio_text="繁殖"),
        _q("g4-c12-5", "G4-C1-2", "basic_choice", "hard",
           "下列词语中书写完全正确的一项是：", "敬佩  奥秘  精疲力竭",
           "A 应为“茂盛”；B 应为“严厉”；D 应为“胸怀”。",
           options=["茂密  茂成  随遇而安", "严历  横七竖八  腾云驾雾", "敬佩  奥秘  精疲力竭", "胸坏  齐头并进  山崩地裂"],
           correct_index=2),
        _q("g4-c12-6", "G4-C1-2", "dictation_spell", "hard",
           "听录音并结合拼音「huī huáng」，写出形容光彩夺目的词语：", "辉煌",
           "“辉煌”左边分别是光字旁和火字旁，都与光亮有关。",
           hint="2 个汉字", audio_text="辉煌", distractors=["灰", "皇", "挥", "惶"]),
    ]

    # G4-C1-3 神话与历史故事成语
    bank["G4-C1-3"] = [
        _q("g4-c13-1", "G4-C1-3", "basic_choice", "basic",
           "“三头六臂、腾云驾雾、神机妙算、各显神通”这组成语通常用来形容：", "神话人物或本领高强的人",
           "这四个成语多源于神话传说（如哪吒、孙悟空、八仙）或形容高超智慧。",
           options=["神话人物或本领高强的人", "风景非常荒凉", "学习粗心大意", "身体非常虚弱"], correct_index=0),
        _q("g4-c13-2", "G4-C1-3", "basic_choice", "basic",
           "成语“精卫填海”“女娲补天”赞美了远古神话人物怎样的精神？", "不畏艰难、坚韧不拔、勇于奉献的精神",
           "中国古代神话集中体现了先民挑战自然、坚韧执着的精神气概。",
           options=["贪图享乐", "不畏艰难、坚韧不拔、勇于奉献的精神", "胆小怕事", "半途而废"], correct_index=1),
        _hanzi_tile_q("g4-c13-3", "G4-C1-3", "medium", "安居乐业", "ān jū lè yè", ["按", "夜"],
                      "“安居乐业”指人民安定地生活、愉快地工作。", seed=404, audio_text="安居乐业"),
        _q("g4-c13-4", "G4-C1-3", "basic_choice", "medium",
           "与“扁鹊治病”“纪昌学射”“西门豹治邺”一样，出自古代历史或寓言典故的成语是：", "铁杵成针",
           "“铁杵成针”出自李白受老媪磨铁棒成针启发而发愤读书的典故。",
           options=["五颜六色", "铁杵成针", "津津有味", "笨手笨脚"], correct_index=1),
        _q("g4-c13-5", "G4-C1-3", "basic_choice", "hard",
           "形容说话声音洪亮、气势宏大，好像大钟和雷声一样的成语是：", "响彻云霄（或声如洪钟）",
           "“响彻云霄”形容声音极为响亮，直达高空；“窃窃私语”“鸦雀无声”均表声音小或安静。",
           options=["窃窃私语", "鸦雀无声", "响彻云霄（或声如洪钟）", "悄无声息"], correct_index=2),
        _q("g4-c13-6", "G4-C1-3", "dictation_spell", "hard",
           "听录音并结合拼音「pò bù jí dài」，用键盘写出这个四字成语：", "迫不及待",
           "“迫不及待”形容心情十分急切，一刻也等不及。",
           hint="4 个汉字", audio_text="迫不及待", distractors=["急", "带", "破", "代"]),
    ]

    # G4-C1-4 听写与看拼音写词语
    bank["G4-C1-4"] = [
        _hanzi_tile_q("g4-c14-1", "G4-C1-4", "basic", "大潮", "dà cháo", ["朝", "嘲"],
                      "“大潮”指钱塘江大潮，“潮”是三点水旁。", seed=405),
        _hanzi_tile_q("g4-c14-2", "G4-C1-4", "basic", "爬山虎", "pá shān hǔ", ["巴", "虑"],
                      "“爬山虎”是一种善于攀爬墙壁的植物，注意“虎”字头写法。", seed=406),
        _hanzi_tile_q("g4-c14-3", "G4-C1-4", "medium", "侵略", "qīn lüè", ["浸", "掠"],
                      "“侵略”的“侵”是单人旁，中间没有竖。", seed=407, audio_text="侵略"),
        _q("g4-c14-4", "G4-C1-4", "dictation_spell", "medium",
           "听录音并结合拼音「ēn huì」，写出正确词语：", "恩惠",
           "“恩惠”指给予或受到的好处。",
           hint="2 个汉字", audio_text="恩惠", distractors=["思", "慧", "惠", "怀"]),
        _q("g4-c14-5", "G4-C1-4", "dictation_spell", "hard",
           "听录音并结合拼音「píng héng」，写出表示平稳对等的词语：", "平衡",
           "“平衡”注意“衡”中间是鱼字底的变形，不要写成“恒”。",
           hint="2 个汉字", audio_text="平衡", distractors=["评", "恒", "行", "平"]),
        _q("g4-c14-6", "G4-C1-4", "dictation_spell", "hard",
           "听录音并结合拼音「lǎn duò」，写出表示不勤快、散漫的词语：", "懒惰",
           "“懒惰”两字均为竖心旁，反义词是“勤劳”。",
           hint="2 个汉字", audio_text="懒惰", distractors=["赖", "随", "堕", "慢"]),
    ]

    # G4-C2-1 条件因果转折关联词运用
    bank["G4-C2-1"] = [
        _q("g4-c21-1", "G4-C2-1", "sentence_choice", "basic",
           "“____蟋蟀并不是挖掘专家，____它的住宅却修建得十分精巧。”应填：", "虽然……但是……",
           "前半句说不是专家，后半句说住宅精巧，构成明显的转折关系。",
           options=["因为……所以……", "虽然……但是……", "如果……就……", "不但……而且……"], correct_index=1),
        _q("g4-c21-2", "G4-C2-1", "sentence_choice", "basic",
           "“____蝙蝠的嘴和耳朵被封住，它____像没头苍蝇一样到处乱撞。”应填：", "如果……就……",
           "前句提出假设实验条件，后句说明产生的结果，属于假设关系。",
           options=["如果……就……", "虽然……可是……", "不但……而且……", "既……又……"], correct_index=0),
        _q("g4-c21-3", "G4-C2-1", "sentence_choice", "medium",
           "“____下多大的雨，边防战士____坚守在岗位上。”最恰当的关联词是：", "无论……都……",
           "表示在任何条件下结果都不会改变，用无条件关联词“无论……都……”。",
           options=["只有……才……", "无论……都……", "因为……所以……", "与其……不如……"], correct_index=1),
        _q("g4-c21-4", "G4-C2-1", "sentence_choice", "medium",
           "“普罗米修斯____忍受鹫鹰啄食肝脏的痛苦，____肯向宙斯屈服归还火种。”应填：", "宁可……也不……",
           "在两种抉择中宁愿吃苦也绝不妥协，用取舍关系“宁可……也不……”。",
           options=["不是……就是……", "宁可……也不……", "既然……就……", "只要……就……"], correct_index=1),
        _q("g4-c21-5", "G4-C2-1", "error_spot", "hard",
           "找出下面句子中关联词搭配的错误：「虽然他平时勤学好问，所以这次阅读竞赛取得了优异成绩。」", "前后是因果关系，应把“虽然”改为“因为”",
           "“勤学好问”是原因，“取得优异成绩”是结果，应搭配“因为……所以……”。",
           options=["应把“所以”删掉且不加关联词", "前后是因果关系，应把“虽然”改为“因为”", "应改为“尽管……还是……”", "句子没有语病"],
           correct_index=1),
        _q("g4-c21-6", "G4-C2-1", "sentence_choice", "hard",
           "“____多读多思、勤做批注，我们的阅读理解能力____能真正提高。”最准确的关联词是：", "只有……才……",
           "强调唯一必要条件，用“只有……才……”。",
           options=["只有……才……", "虽然……但是……", "即使……也……", "哪怕……也……"], correct_index=0),
    ]

    # G4-C2-2 反问句与陈述句转换
    bank["G4-C2-2"] = [
        _q("g4-c22-1", "G4-C2-2", "sentence_choice", "basic",
           "把反问句“钱塘江大潮难道不是天下奇观吗？”改为陈述句，正确的是：", "钱塘江大潮是天下奇观。",
           "去掉“难道”“不”“吗”，问号改句号，原意是肯定“是天下奇观”。",
           options=["钱塘江大潮不是天下奇观。", "钱塘江大潮是天下奇观。", "钱塘江大潮怎么是天下奇观？", "钱塘江大潮是天下奇观吗？"],
           correct_index=1),
        _q("g4-c22-2", "G4-C2-2", "sentence_choice", "basic",
           "把陈述句“为中华之崛起而读书，这是远大的志向。”改为反问句，正确的是：", "为中华之崛起而读书，这难道不是远大的志向吗？",
           "肯定陈述句改反问句：加上反问词“难道”和否定词“不是”，句末加“吗？”。",
           options=["为中华之崛起而读书，这不是远大的志向。", "为中华之崛起而读书，这难道不是远大的志向吗？", "为中华之崛起而读书，这难道是远大的志向吗？", "为中华之崛起而读书，是不是志向？"],
           correct_index=1),
        _q("g4-c22-3", "G4-C2-2", "sentence_choice", "medium",
           "“看到满山火红的杜鹃花，谁能不赞叹大自然的神奇呢？”这句话表达的真实意思是：", "看到满山火红的杜鹃花，每个人都赞叹大自然的神奇。",
           "“谁能不……”相当于“人人都会……”，用反问加强肯定语气。",
           options=["没有人赞叹大自然的神奇。", "看到满山火红的杜鹃花，每个人都赞叹大自然的神奇。", "不知道有没有人赞叹。", "杜鹃花并不神奇。"],
           correct_index=1),
        _q("g4-c22-4", "G4-C2-2", "sentence_choice", "medium",
           "与陈述句相比，使用反问句“蟋蟀怎么会有建筑工具呢？”在表达上有什么好处？", "语气更强烈，更能突出蟋蟀完全靠柔弱的脚挖掘住宅的了不起",
           "反问句用疑问的形式表达确定的意思，比普通陈述句语气更强烈、情感更鲜明。",
           options=["让读者不知道答案", "语气更强烈，更能突出蟋蟀完全靠柔弱的脚挖掘住宅的了不起", "为了多凑几个字", "表示作者自己也不知道蟋蟀有没有工具"],
           correct_index=1),
        _q("g4-c22-5", "G4-C2-2", "sentence_choice", "hard",
           "把“人类的老祖宗盘古，用他的整个身体创造了美丽的世界”改为反问句，正确的是：", "人类的老祖宗盘古，难道不是用他的整个身体创造了美丽的世界吗？",
           "保持肯定原意不变，添加“难道不是……吗？”。",
           options=["人类的老祖宗盘古，难道是用他的整个身体创造了美丽的世界吗？", "人类的老祖宗盘古，难道不是用他的整个身体创造了美丽的世界吗？", "盘古为什么没有创造美丽的世界？", "盘古不是创造了美丽的世界。"],
           correct_index=1),
        _q("g4-c22-6", "G4-C2-2", "sentence_choice", "hard",
           "把反问句“面对同胞受辱，我们怎能袖手旁观？”改为陈述句，最准确的是：", "面对同胞受辱，我们绝不能袖手旁观。",
           "原反问句中没有“不”，改陈述句时需加上否定词“不能/绝不能”。",
           options=["面对同胞受辱，我们可以袖手旁观。", "面对同胞受辱，我们绝不能袖手旁观。", "面对同胞受辱，我们怎能不袖手旁观？", "面对同胞受辱，我们在袖手旁观。"],
           correct_index=1),
    ]

    # G4-C2-3 设问排比与连续动作描写
    bank["G4-C2-3"] = [
        _q("g4-c23-1", "G4-C2-3", "sentence_choice", "basic",
           "“在漆黑的夜里，飞机是怎么做到安全飞行的呢？秘密在于科学家模仿蝙蝠探路装上了雷达。”运用的修辞手法是：", "设问",
           "先提出问题，紧接着自己回答出来，以引起读者注意和思考，属于设问。",
           options=["反问", "设问", "比喻", "拟人"], correct_index=1),
        _q("g4-c23-2", "G4-C2-3", "sentence_choice", "basic",
           "“那条白线很快向我们移来，逐渐拉长，变粗，横贯江面。”这句话通过一连串动词写出了：", "钱塘江大潮由远及近、气势迅速壮大的动态变化",
           "“移来、拉长、变粗、横贯”连续四个动词，精准展现出潮水推进的动态过程。",
           options=["江面非常平静", "钱塘江大潮由远及近、气势迅速壮大的动态变化", "白线是一根绳子", "江水已经退去了"],
           correct_index=1),
        _q("g4-c23-3", "G4-C2-3", "sentence_choice", "medium",
           "“漓江的水真静啊，静得让你感觉不到它在流动；漓江的水真清啊，清得可以看见江底的沙石；漓江的水真绿啊，绿得仿佛那是一块无瑕的翡翠。”主要运用了：", "排比（兼有比喻）",
           "三个结构相同、句式一致的分句排列在一起增强语势，属于排比。",
           options=["设问", "反问", "排比（兼有比喻）", "夸张"], correct_index=2),
        _q("g4-c23-4", "G4-C2-3", "sentence_choice", "medium",
           "“爬山虎的脚触着墙的时候，六七根细丝的头上就变成小圆片，巴住墙。细丝原先是直的，现在弯曲了，把爬山虎的嫩茎拉一把，使它紧贴在墙上。”其中最能体现爬山虎爬墙有力量的连续动词是：", "触、变、巴、拉、贴",
           "叶圣陶先生用“触、变、巴、拉、贴”五个精准动词，把爬山虎一脚一脚往上爬的过程写活了。",
           options=["脚、墙、细丝、圆片", "触、变、巴、拉、贴", "原先、现在、时候", "六七根、嫩茎"], correct_index=1),
        _q("g4-c23-5", "G4-C2-3", "sentence_choice", "hard",
           "设问句与反问句最大的区别是什么？", "设问句自问自答；反问句只问不答，答案已经隐含在问句中",
           "设问有问有答；反问无疑而问，答案就在句子反面。",
           options=["设问句没有问号，反问句有问号", "设问句自问自答；反问句只问不答，答案已经隐含在问句中", "两者没有任何区别", "反问句必须自问自答"],
           correct_index=1),
        _q("g4-c23-6", "G4-C2-3", "sentence_choice", "hard",
           "下列哪一句把“小守门员接球”的连续动作写得最具体传神？", "只见他微微屈膝，死死盯住飞来的足球，猛地向右侧扑出去，双手稳稳将球抱在怀里。",
           "“屈膝、盯住、扑出去、抱在怀里”四个连贯动作把扑球瞬间刻画得栩栩如生。",
           options=["小守门员一下子就把球接住了，真厉害。", "只见他微微屈膝，死死盯住飞来的足球，猛地向右侧扑出去，双手稳稳将球抱在怀里。", "足球飞过来了，守门员站在球门前。", "他是个非常优秀的足球守门员。"],
           correct_index=1),
    ]

    # G4-C2-4 病句修改（搭配不当与成分残缺）
    bank["G4-C2-4"] = [
        _q("g4-c24-1", "G4-C2-4", "error_spot", "basic",
           "找出下面病句的病因：「经过半学期的努力，我的写作水平明显增加了。」", "动宾搭配不当（“水平”应搭配“提高”，不能搭配“增加”）",
           "“水平”与“增加”搭配不当，应把“增加”改为“提高”。",
           options=["缺少主语", "动宾搭配不当（“水平”应搭配“提高”，不能搭配“增加”）", "前后矛盾", "语序颠倒"],
           correct_index=1),
        _q("g4-c24-2", "G4-C2-4", "error_spot", "basic",
           "找出下面病句的病因：「在老师的耐心帮助下，使我克服了朗读卡顿的毛病。」", "成分残缺（滥用介词“在……下”和“使”导致缺主语）",
           "删去“使”字，让“我”成为句子的主语。",
           options=["成分残缺（滥用介词“在……下”和“使”导致缺主语）", "分类不当", "否定不当", "用词重复"],
           correct_index=0),
        _q("g4-c24-3", "G4-C2-4", "error_spot", "medium",
           "找出下面病句的病因：「学校开展的“书香校园”活动，增强了同学们的阅读兴趣。」", "搭配不当（“兴趣”应搭配“激发”或“培养”，或把“兴趣”改为“意识”）",
           "“增强……兴趣”搭配不当，应改为“激发了同学们的阅读兴趣”。",
           options=["缺少宾语", "搭配不当（“兴趣”应搭配“激发”或“培养”，或把“兴趣”改为“意识”）", "语义重复", "指代不明"],
           correct_index=1),
        _q("g4-c24-4", "G4-C2-4", "error_spot", "medium",
           "找出下面病句的病因：「每个小学生都应该养成上课认真听讲、专心思考。」", "成分残缺（缺少宾语中心语，句末应加上“的好习惯”）",
           "“养成……”后面缺少对应的宾语“的好习惯”。",
           options=["缺少主语", "成分残缺（缺少宾语中心语，句末应加上“的好习惯”）", "前后矛盾", "语序不当"],
           correct_index=1),
        _q("g4-c24-5", "G4-C2-4", "sentence_choice", "hard",
           "下列句子中没有语病的一项是：", "科学家经过反复研究，终于揭开了蝙蝠夜间飞行的秘密。",
           "A 缺主语；B “发扬”与“精神”才搭配（或“发挥作用”）；D 缺宾语“的称号”。",
           options=["读了《观潮》这篇课文，让我感受到钱塘江大潮的雄伟。", "班干部在班级管理中发扬了很好的带头作用。", "科学家经过反复研究，终于揭开了蝙蝠夜间飞行的秘密。", "他被评为学校“阅读小达人”。"],
           correct_index=2),
        _q("g4-c24-6", "G4-C2-4", "error_spot", "hard",
           "找出下面病句的病因：「秋天的北京是一个美丽的季节。」", "主宾搭配不当（“北京”是地方不是“季节”，应改为“北京的秋天”）",
           "主语“北京”和宾语“季节”不搭配，调换为“北京的秋天是一个美丽的季节”即可。",
           options=["缺少谓语", "主宾搭配不当（“北京”是地方不是“季节”，应改为“北京的秋天”）", "语义重复", "否定不当"],
           correct_index=1),
    ]

    # G4-C3-1 山水田园与哲理古诗（《题西林壁》《暮江吟》《宿新市徐公店》）
    bank["G4-C3-1"] = [
        _poem_tile_q("g4-c31-1", "G4-C3-1", "basic",
                     "点选字块，补全苏轼《题西林壁》哲理名句：「不识庐山真面目，____。」",
                     "只缘身在此山中", ["原", "生"],
                     "“缘”是因为的意思；由于身处庐山之中，视野受限才看不清庐山全貌。", seed=431),
        _poem_tile_q("g4-c31-2", "G4-C3-1", "basic",
                     "点选字块，补全白居易《暮江吟》名句：「可怜九月初三夜，____。」",
                     "露似真珠月似弓", ["珠", "珍"],
                     "把晶莹的露珠比作珍珠（真珠），把弯弯的新月比作弯弓。", seed=432),
        _q("g4-c31-3", "G4-C3-1", "reading_choice", "medium",
           "白居易《暮江吟》“一道残阳铺水中，半江瑟瑟半江红”中，“可怜九月初三夜”的“可怜”意思是：", "可爱",
           "古诗中“可怜”常指“可爱、令人喜爱”，并非现代汉语的“值得同情”。",
           options=["值得同情", "可爱", "非常凄凉", "可惜"], correct_index=1),
        _q("g4-c31-4", "G4-C3-1", "reading_choice", "medium",
           "苏轼《题西林壁》“横看成岭侧成峰，远近高低各不同”蕴含的人生哲理是：", "看待事物要跳出局部、从多个角度全面客观地观察，才能认清真相（当局者迷，旁观者清）",
           "站在不同角度看到的事物样子不同，只有全面客观才能看清全貌。",
           options=["庐山的山路非常难走", "看待事物要跳出局部、从多个角度全面客观地观察，才能认清真相（当局者迷，旁观者清）", "旅游时一定要拍照", "爬山越快越好"],
           correct_index=1),
        _q("g4-c31-5", "G4-C3-1", "poem_fill", "hard",
           "精准默写苏轼《题西林壁》末句：「不识庐山真面目，________。」",
           "只缘身在此山中",
           "注意是绞丝旁的“缘”（因为），不要写成“原”。",
           hint="7 个汉字，出自《题西林壁》", distractors=["原", "生", "再", "重"]),
        _q("g4-c31-6", "G4-C3-1", "poem_fill", "hard",
           "精准默写杨万里《宿新市徐公店》末句：「儿童急走追黄蝶，________。」",
           "飞入菜花无处寻",
           "黄蝴蝶飞进金黄的油菜花丛中，颜色融为一体再也找不到了。",
           hint="7 个汉字，出自《宿新市徐公店》", distractors=["采", "花", "处", "找"]),
    ]

    # G4-C3-2 边塞与送别古诗（《出塞》《凉州词》《芙蓉楼送辛渐》）
    bank["G4-C3-2"] = [
        _poem_tile_q("g4-c32-1", "G4-C3-2", "basic",
                     "点选字块，补全王昌龄《出塞》名句：「但使龙城飞将在，____。」",
                     "不教胡马度阴山", ["渡", "交"],
                     "只要汉代飞将军李广那样英勇的良将还在，就绝不许敌军战马越过阴山。", seed=433),
        _poem_tile_q("g4-c32-2", "G4-C3-2", "basic",
                     "点选字块，补全王昌龄《芙蓉楼送辛渐》名句：「洛阳亲友如相问，____。」",
                     "一片冰心在玉壶", ["兵", "胡"],
                     "以冰心玉壶自喻，表明自己廉洁正直、清白高洁的品格。", seed=434),
        _q("g4-c32-3", "G4-C3-2", "reading_choice", "medium",
           "王翰《凉州词》“醉卧沙场君莫笑，古来征战几人回”表现了将士们怎样的豪情？", "视死如归、豪放旷达的英雄气概与边塞征战的悲壮",
           "将士们在出征前开怀畅饮、把生死置之度外，悲壮而豪迈。",
           options=["贪杯喝醉不想打仗", "视死如归、豪放旷达的英雄气概与边塞征战的悲壮", "害怕上战场而哭泣", "在沙漠里快乐旅游"],
           correct_index=1),
        _q("g4-c32-4", "G4-C3-2", "reading_choice", "medium",
           "高适《别董大》中激励友人不必因离别和暂时失意而发愁的千古名句是：", "莫愁前路无知己，天下谁人不识君？",
           "一改送别诗的悲伤格调，显得慷慨豪迈、催人奋进。",
           options=["劝君更尽一杯酒，西出阳关无故人。", "莫愁前路无知己，天下谁人不识君？", "桃花潭水深千尺，不及汪伦送我情。", "孤帆远影碧空尽，唯见长江天际流。"],
           correct_index=1),
        _q("g4-c32-5", "G4-C3-2", "poem_fill", "hard",
           "精准默写王昌龄《出塞》末句：「但使龙城飞将在，________。」",
           "不教胡马度阴山",
           "注意是“度阴山”的“度”，不加三点水。",
           hint="7 个汉字，出自《出塞》", distractors=["渡", "交", "湖", "山"]),
        _q("g4-c32-6", "G4-C3-2", "poem_fill", "hard",
           "精准默写王昌龄《芙蓉楼送辛渐》末句：「洛阳亲友如相问，________。」",
           "一片冰心在玉壶",
           "“冰心”与“玉壶”象征纯洁高尚的节操。",
           hint="7 个汉字，出自《芙蓉楼送辛渐》", distractors=["兵", "王", "湖", "胡"]),
    ]

    # G4-C3-3 神话与劝学小古文（《精卫填海》《王戎不取道旁李》《囊萤夜读》）
    bank["G4-C3-3"] = [
        _q("g4-c33-1", "G4-C3-3", "reading_choice", "basic",
           "《精卫填海》中“女娃游于东海，溺而不返，故为精卫”的“溺”和“故”分别是什么意思？", "溺水、淹没；因此",
           "女娃在东海游泳溺水未能回来，因此化为精卫鸟。",
           options=["溺爱；故事", "溺水、淹没；因此", "逃跑；故乡", "潜水；原来"], correct_index=1),
        _q("g4-c33-2", "G4-C3-3", "reading_choice", "basic",
           "《王戎不取道旁李》中“诸儿竞走取之，唯戎不动”的“竞走”意思是：", "争着跑过去",
           "“竞”是争着，“走”在古文中是跑，即大家争先恐后跑过去摘李子。",
           options=["比赛竞走运动", "争着跑过去", "慢慢走开", "并排站着"], correct_index=1),
        _q("g4-c33-3", "G4-C3-3", "reading_choice", "medium",
           "王戎为什么断定路边的李子是苦李（“树在道边而多子，此必苦李”）？", "李子树长在人来人往的大路边却还留着很多果子，如果是甜李早被人摘光了",
           "王戎善于观察环境并进行严密的逻辑推理，不盲从跟风。",
           options=["他之前偷偷尝过一口", "李子树长在人来人往的大路边却还留着很多果子，如果是甜李早被人摘光了", "他不喜欢吃李子", "树太高他摘不到"],
           correct_index=1),
        _q("g4-c33-4", "G4-C3-3", "reading_choice", "medium",
           "《囊萤夜读》“家贫不常得油，夏月则练囊盛数十萤火以照书”中，车胤用什么照明读书？", "用白色薄绢口袋装几十只萤火虫照明",
           "“练囊”即白色薄绢口袋，体现了车胤克服贫苦条件勤奋苦读的精神。",
           options=["点蜡烛照明", "用白色薄绢口袋装几十只萤火虫照明", "站在月光下读书", "借邻居家的灯光"],
           correct_index=1),
        _poem_tile_q("g4-c33-5", "G4-C3-3", "hard",
                     "点选字块，补全《精卫填海》名句：「常衔西山之木石，____。」",
                     "以堙于东海", ["因", "烟"],
                     "“堙”读 yīn，是填塞的意思。", seed=435),
        _q("g4-c33-6", "G4-C3-3", "poem_fill", "hard",
           "精准默写《王戎不取道旁李》中王戎推理的八字名句：「树在道边而多子，________。」",
           "此必苦李",
           "“此必苦李”即这一定是苦李子。",
           hint="4 个汉字", distractors=["比", "心", "古", "梨"]),
    ]

    # G4-C3-4 八字成语与名言警句
    bank["G4-C3-4"] = [
        _poem_tile_q("g4-c34-1", "G4-C3-4", "basic",
                     "点选字块，补全韩愈劝学名言：「人非生而知之者，____？」",
                     "孰能无惑", ["熟", "或"],
                     "人不是生下来就什么都懂的，谁能没有疑惑呢？", seed=436),
        _q("g4-c34-2", "G4-C3-4", "reading_choice", "basic",
           "“尺有所短，寸有所长”这句八字成语告诉我们：", "每个人都有自己的长处和短处，要学会取长补短",
           "比喻人和事物各有长短，不可骄傲自满，应虚心向他人学习。",
           options=["尺子比寸更短", "每个人都有自己的长处和短处，要学会取长补短", "买尺子要买长的", "人没有缺点"],
           correct_index=1),
        _q("g4-c34-3", "G4-C3-4", "reading_choice", "medium",
           "形容在精密计算或科学实验中“开头只有极小的偏差，结果却会造成巨大错误”的八字成语是：", "差之毫厘，谬以千里。",
           "“差之毫厘，谬以千里”提醒我们做事必须严谨细致。",
           options=["一言既出，驷马难追。", "差之毫厘，谬以千里。", "机不可失，时不再来。", "比上不足，比下有余。"],
           correct_index=1),
        _q("g4-c34-4", "G4-C3-4", "reading_choice", "medium",
           "《礼记》中包涵学习的五个步骤“博学之，审问之，慎思之，明辨之，笃行之”，其中“审问”指的是：", "遇到不懂的地方要详细地向人请教追问",
           "广泛学习、详细提问、慎重思考、明确辨别、切实履行。",
           options=["审问犯人", "遇到不懂的地方要详细地向人请教追问", "考试出试卷", "大声背书"],
           correct_index=1),
        _q("g4-c34-5", "G4-C3-4", "poem_fill", "hard",
           "听录音或根据提示，精准默写《论语》好问名言：「________，不耻下问。」",
           "敏而好学",
           "“敏而好学，不耻下问”强调聪敏勤学且虚心请教。",
           hint="4 个汉字", audio_text="敏而好学，不耻下问。", audio_voice="zh-CN-YunxiNeural", distractors=["每", "号", "字", "觉"]),
        _q("g4-c34-6", "G4-C3-4", "poem_fill", "hard",
           "精准默写关于守信诺言的八字成语下句：「一言既出，________。」",
           "驷马难追",
           "一句话说出口，就是四匹马拉的车也追不回来，形容说话算话。",
           hint="4 个汉字", distractors=["四", "妈", "男", "退"]),
    ]

    # G4-C4-1 起因经过结果概括主要内容
    p_g4_event = (
        "假日里，我和爸爸去爬天都峰。站在山脚下抬头望，峰顶在云彩上面，石阶像从天上挂下来似的，我禁不住发颤。"
        "这时一位白发苍苍的老爷爷也来爬山，我们互相鼓励，决定一起往上爬。"
        "我手脚并用，拉着铁链奋力攀登，终于和老爷爷、爸爸一起登上了天都峰顶。在鲫鱼背前，我们还愉快地合影留念。"
    )
    bank["G4-C4-1"] = [
        _q("g4-c41-1", "G4-C4-1", "reading_choice", "basic",
           "按“起因→经过→结果”梳理这篇短文，故事的“起因”是：", "假日里“我”和爸爸去爬陡峭的天都峰，站在山脚下心里有些发怵",
           "第一句交代了时间、人物、地点以及看到天都峰高耸陡峭时的畏难心理（起因）。",
           options=["在山顶合影留念", "假日里“我”和爸爸去爬陡峭的天都峰，站在山脚下心里有些发怵", "老爷爷下山回家了", "买了一张公园门票"],
           correct_index=1, passage=p_g4_event),
        _q("g4-c41-2", "G4-C4-1", "reading_choice", "basic",
           "把起因、经过、结果连起来，这段话的主要内容是：", "“我”和爸爸去爬陡峭的天都峰，与一位白发老爷爷互相鼓励、奋力攀登，最终成功登上峰顶。",
           "抓住核心人物（我、老爷爷、爸爸）+ 起因（爬陡峭天都峰）+ 经过（互相鼓励奋力爬）+ 结果（登上峰顶）。",
           options=["天都峰的石阶非常陡峭，像从天上挂下来一样。", "“我”和爸爸去爬陡峭的天都峰，与一位白发老爷爷互相鼓励、奋力攀登，最终成功登上峰顶。", "老爷爷的年纪很大，头发都白了。", "爸爸帮“我”拍了一张照片。"],
           correct_index=1, passage=p_g4_event),
        _q("g4-c41-3", "G4-C4-1", "reading_choice", "medium",
           "文中“石阶像从天上挂下来似的，我禁不住发颤”在文中的作用是：", "突出天都峰的高和陡，为后文“我”和老爷爷克服困难爬上峰顶作铺垫",
           "先写山高路陡令人生畏，更能衬托出后来攀登的勇敢与不易。",
           options=["说明“我”穿的衣服太少很冷", "突出天都峰的高和陡，为后文“我”和老爷爷克服困难爬上峰顶作铺垫", "说明石阶坏了不能走", "与后文没有任何关系"],
           correct_index=1, passage=p_g4_event),
        _q("g4-c41-4", "G4-C4-1", "reading_choice", "medium",
           "当一篇文章写了好几件事时，我们应该怎样把握文章的主要内容？", "先把每件事弄清楚，再把几件事连起来归纳（或抓住最核心的主线）",
           "多事件文章可先分段概括每件事，再串联合并。",
           options=["只看第一件事，后面的全不管", "先把每件事弄清楚，再把几件事连起来归纳（或抓住最核心的主线）", "只抄最后一个自然段", "数一数一共有多少个自然段"],
           correct_index=1),
        _q("g4-c41-5", "G4-C4-1", "reading_short", "hard",
           "【阅读简答】“我”一开始看着天都峰“禁不住发颤”，后来为什么能成功爬上峰顶？请结合短文内容简要回答。",
           "因为“我”遇到了白发苍苍还来爬山的老爷爷，受到鼓舞，两人互相汲取力量，手脚并用奋力攀登，最终战胜了困难。",
           "答题思路：写出老爷爷的榜样激励 + 两人互相鼓励 + 自己手脚并用奋力攀登。",
           passage=p_g4_event,
           rubric_keywords=[["老爷爷", "鼓励", "力量"], ["手脚并用", "奋力", "攀登", "坚持", "克服"]],
           min_chars=14,
           sample_answer="因为“我”看到白发苍苍的老爷爷也勇敢来爬山，两人互相鼓励汲取力量，“我”手脚并用奋力攀登，最终战胜了畏惧登上了峰顶。",
           scaffolds=[
               "开头可用：因为“我”遇到了一位白发苍苍的老爷爷……",
               "关键词提示：互相鼓励、手脚并用、奋力攀登、战胜困难",
               "结尾感悟：从别人身上汲取了克服困难的勇气和力量。",
           ]),
        _q("g4-c41-6", "G4-C4-1", "reading_choice", "hard",
           "爬上峰顶后，老爷爷和“我”互相道谢，他们为什么要向对方道谢？", "因为他们都从对方的勇气中汲取了战胜困难的信心和力量",
           "一老一少互相激励，共同战胜了险峰。",
           options=["因为对方帮自己背了书包", "因为他们都从对方的勇气中汲取了战胜困难的信心和力量", "只是客套礼貌", "因为对方借了登山杖"],
           correct_index=1, passage=p_g4_event),
    ]

    # G4-C4-2 批注阅读与多角度提问策略
    p_g4_annot = (
        "突然，一只老麻雀从一棵树上飞下来，像一块石头似的落在猎狗面前。"
        "它挓挲起全身的羽毛，绝望地尖叫着，用自己的身躯掩护着身后刚从巢里掉下来的小麻雀。"
        "可是因为紧张，它浑身发抖，发出嘶哑的声音。在它看来，猎狗是个多么庞大的怪物啊！然而它不能安然地站在高高的没有危险的树枝上，一种强大的力量使它飞了下来。"
    )
    bank["G4-C4-2"] = [
        _q("g4-c42-1", "G4-C4-2", "reading_choice", "basic",
           "一位同学在“像一块石头似的落在猎狗面前”旁写下批注：“把老麻雀比作石头，写出它飞落时毫不犹豫、非常坚定勇敢！”这属于哪种批注角度？", "赏析写得好的词句及表达效果",
           "批注可以从有疑问的地方、写得好的地方、有启发的地方等角度切入，这里是赏析比喻句的妙处。",
           options=["解释生字拼音", "赏析写得好的词句及表达效果", "挑文章的错别字", "计算字数"],
           correct_index=1, passage=p_g4_annot),
        _q("g4-c42-2", "G4-C4-2", "reading_choice", "basic",
           "文中“一种强大的力量使它飞了下来”中的“强大的力量”指的是：", "伟大的母爱（保护幼小的本能与爱）",
           "正是无私伟大的母爱让弱小的老麻雀战胜恐惧，直面庞大的猎狗。",
           options=["树枝被风吹断的力量", "伟大的母爱（保护幼小的本能与爱）", "地球引力的力量", "老麻雀想和猎狗赛跑"],
           correct_index=1, passage=p_g4_annot),
        _q("g4-c42-3", "G4-C4-2", "reading_choice", "medium",
           "阅读时我们可以从“课文内容”“课文写法”“联系生活启示”三个角度提问。下面哪个问题属于针对“课文写法”提问？", "作者为什么一边写老麻雀勇敢掩护，一边又写它“浑身发抖、绝望尖叫”？这样写有什么好处？",
           "探究作者为何这样写、有什么表达效果，属于针对“写法”的高质量提问。",
           options=["老麻雀是从哪儿飞下来的？", "作者为什么一边写老麻雀勇敢掩护，一边又写它“浑身发抖、绝望尖叫”？这样写有什么好处？", "猎狗最后有没有吃掉小麻雀？", "“挓挲”这两个字怎么读？"],
           correct_index=1, passage=p_g4_annot),
        _q("g4-c42-4", "G4-C4-2", "reading_choice", "medium",
           "针对上一题：作者既写老麻雀的勇敢，又写它“浑身发抖”，这样写的好处是：", "真实地写出老麻雀面对庞大猎狗时的本能恐惧，反衬出母爱让它战胜恐惧的伟大",
           "不回避弱小者的恐惧，反而让它挺身而出的勇气更加真实震撼。",
           options=["前后矛盾，作者写错了", "真实地写出老麻雀面对庞大猎狗时的本能恐惧，反衬出母爱让它战胜恐惧的伟大", "说明天气非常寒冷", "说明老麻雀生病了"],
           correct_index=1, passage=p_g4_annot),
        _q("g4-c42-5", "G4-C4-2", "reading_short", "hard",
           "【阅读简答】请给短文中「像一块石头似的落在猎狗面前」这句话写一段 15～40 字的阅读批注（说说这句话用什么修辞写出了老麻雀怎样的形象）。",
           "这句话运用比喻，把老麻雀比作落下的石头，生动写出了老麻雀飞下来救幼鸟时的疾速、果断与奋不顾身，体现了伟大的母爱。",
           "批注思路：点明比喻修辞 + 写出老麻雀动作的果断勇敢 + 体会母爱的伟大。",
           passage=p_g4_annot,
           rubric_keywords=[["比喻", "石头", "比作"], ["勇敢", "果断", "坚定", "毫不犹豫", "奋不顾身", "母爱", "救"]],
           min_chars=14,
           sample_answer="运用比喻的修辞手法，把老麻雀比作石头，生动写出了它冲下来保护小麻雀时的迅速、坚定和奋不顾身，展现了母爱的伟大。",
           scaffolds=[
               "批注句式：这句话运用了比喻修辞，把老麻雀比作……",
               "好词锦囊：毫不犹豫、奋不顾身、坚定果断、伟大的母爱",
               "体会支架：生动写出了老麻雀救小麻雀时的……，让我体会到……",
           ]),
        _q("g4-c42-6", "G4-C4-2", "reading_choice", "hard",
           "我们在做阅读批注时，下列哪种做法最科学有效？", "边读边圈画关键词句，在空白处简明记下自己的感受、疑问或赏析，读完再结合批注加深理解",
           "不动笔墨不读书，圈画+页边简明批注是极佳的精读习惯。",
           options=["把整篇课文一字不差抄在旁边", "边读边圈画关键词句，在空白处简明记下自己的感受、疑问或赏析，读完再结合批注加深理解", "只画笑脸不写任何字", "把书涂黑看不清原文"],
           correct_index=1),
    ]

    # G4-C4-3 人物连续动作与神态心理体会
    bank["G4-C4-3"] = [
        _q("g4-c43-1", "G4-C4-3", "reading_choice", "basic",
           "“我笨拙地表演着，把大陀螺抽得东倒西歪，直到被叔叔的大陀螺彻底撞翻，我羞得恨不得找个地缝钻进去。”主要刻画了“我”怎样的心情？", "尴尬、羞愧与懊恼",
           "“羞得恨不得找个地缝钻进去”生动表现了比赛惨败后的羞愧难当。",
           options=["骄傲自豪", "尴尬、羞愧与懊恼", "悠闲自在", "欣喜若狂"], correct_index=1),
        _q("g4-c43-2", "G4-C4-3", "reading_choice", "basic",
           "“大鹅伸长脖子，瞪圆眼睛，啪嗒啪嗒地拍打着翅膀朝我冲过来。”这句话主要通过什么描写表现鹅的凶悍？", "动作描写和神态描写",
           "“伸长、拍打、冲”是动作，“瞪圆眼睛”是神态，活画出一只嚣张凶悍的大白鹅。",
           options=["语言描写", "心理描写", "动作描写和神态描写", "环境描写"], correct_index=2),
        _q("g4-c43-3", "G4-C4-3", "reading_choice", "medium",
           "在《扁鹊治病》《纪昌学射》中，纪昌“每天站在织布机下面，聚精会神地盯着来回穿梭的梭子，两年后连眨眼都忘了”，这组描写体现了纪昌：", "学习本领态度极度专注、有恒心和毅力",
           "通过苦练眼力的细节，突显纪昌勤学苦练、持之以恒的品格。",
           options=["喜欢看别人织布", "学习本领态度极度专注、有恒心和毅力", "眼睛生病了", "不想学射箭"],
           correct_index=1),
        _q("g4-c43-4", "G4-C4-3", "reading_choice", "medium",
           "要表现一个人“收到心爱礼物时高兴极了”，下面哪组连续动作和神态最传神？", "她眼睛一下子亮了起来，迫不及待地拆开彩带，捧起画册欢呼着在原地转了两个圈。",
           "眼神发亮+迫不及待拆彩带+捧起画册欢呼转圈，把欣喜若狂演得淋漓尽致。",
           options=["她收到礼物后特别特别高兴。", "她看了一眼礼物，放在了桌子上。", "她眼睛一下子亮了起来，迫不及待地拆开彩带，捧起画册欢呼着在原地转了两个圈。", "她说了一句谢谢就去写作业了。"],
           correct_index=2),
        _q("g4-c43-5", "G4-C4-3", "micro_writing", "hard",
           "【微片段写作】请运用至少 3 个连续的动词和神态/心理细节，写一段 55～100 字的话，表现「自己或同学参加比赛（如跳绳、投篮、拔河、朗诵）最精彩或最紧张的一瞬间」。",
           "包含至少 3 个连续动作与神态/心理描写，画面紧张生动。",
           "写作提示：分解动作（如握绳、起跳、加速，或瞄准、起跳、投出），配上眼神与心跳。",
           rubric_keywords=[["握", "抓", "盯", "跳", "跑", "投", "冲", "挥", "迈", "拉"], ["心", "眼", "汗", "咬牙", "屏住呼吸", "欢呼", "紧张"]],
           min_chars=50,
           sample_answer="哨声一响，我双手紧握绳柄，手腕飞快摇动，双脚像装了弹簧似的连续跃起。绳子在耳边“呼呼”作响，汗珠顺着脸颊滑落，我咬紧牙关屏住呼吸拼命加速，直到终场哨响才长舒一口气！",
           scaffolds=[
               "开头可用：哨声一响，我深吸一口气，双手紧握……",
               "好词锦囊：聚精会神、目不转睛、屏住呼吸、身轻如燕、全力以赴",
               "动作链支架：先写准备动作（盯住/握紧）→ 再写爆发动作（跃起/挥动/冲刺）→ 最后写结果与心情",
           ]),
        _q("g4-c43-6", "G4-C4-3", "reading_choice", "hard",
           "通过人物的动作、语言、神态去揣摩人物心情时，最重要的是：", "结合上下文的具体情境，把外在动作神态与内在心理变化联系起来",
           "外在言行是内在心理的镜子，结合语境才能准确体会情感。",
           options=["脱离课文随便猜测", "结合上下文的具体情境，把外在动作神态与内在心理变化联系起来", "只看标点符号", "只背词语解释"],
           correct_index=1),
    ]

    # G4-C4-4 细节升格与80字微片段写作
    bank["G4-C4-4"] = [
        _q("g4-c44-1", "G4-C4-4", "reading_choice", "basic",
           "写《推荐一个好地方》时，怎样才能让读者也想去这个地方看看？", "写出这个地方最独特的 2～3 处景物或好玩之处，调动视觉、听觉、味觉把画面写鲜活",
           "突出独特亮点+多感官细节描写，最能打动读者。",
           options=["只写这个地方的地址和路牌", "写出这个地方最独特的 2～3 处景物或好玩之处，调动视觉、听觉、味觉把画面写鲜活", "反复写十遍“这里真好玩”", "照抄地图上的名字"],
           correct_index=1),
        _q("g4-c44-2", "G4-C4-4", "reading_choice", "basic",
           "把“雨下得很大”升格为有画面感的句子，下面哪一句最好？", "豆大的雨点噼里啪啦地砸在窗户上，天地间顷刻间挂起了一道白茫茫的雨帘。",
           "既有视觉（豆大、白茫茫的雨帘），又有听觉（噼里啪啦砸在窗上），画面感极强。",
           options=["外面的雨下得太大太大了。", "今天下了一场非常大的大雨。", "豆大的雨点噼里啪啦地砸在窗户上，天地间顷刻间挂起了一道白茫茫的雨帘。", "下雨了，地上全都湿了。"],
           correct_index=2),
        _q("g4-c44-3", "G4-C4-4", "reading_choice", "medium",
           "写《我的家人（小小“动物园”）》时，如果把爱游泳的弟弟比作“小泥鳅”，应该重点写什么事例？", "写弟弟一跳进泳池就灵活地钻来钻去、怎么抓也抓不住的有趣场景",
           "找准家人与动物的相似点（游泳灵活像泥鳅），再用典型场景支撑。",
           options=["写弟弟在家里安静地睡午觉", "写弟弟一跳进泳池就灵活地钻来钻去、怎么抓也抓不住的有趣场景", "写菜市场怎么买泥鳅", "写弟弟不喜欢碰水"],
           correct_index=1),
        _q("g4-c44-4", "G4-C4-4", "reading_choice", "medium",
           "写一件令自己“心儿怦怦跳”的事情时，高分秘诀是：", "随着事情的发展，一步步写出自己心情从“担忧→紧张到极点→松了一口气”的起伏过程，并配上身体反应",
           "写出心理变化曲线与心跳、出汗、发抖等生理细节，文章最真实感人。",
           options=["从头到尾只写“我的心怦怦跳”六个字", "随着事情的发展，一步步写出自己心情从“担忧→紧张到极点→松了一口气”的起伏过程，并配上身体反应", "只写别人的事情，不写自己的感受", "把三年前所有的事都记成流水账"],
           correct_index=1),
        _q("g4-c44-5", "G4-C4-4", "micro_writing", "hard",
           "【微片段写作】请从「着急、开心、害怕、生气」中任选一种心情，不用直接堆砌形容词，而是通过 60～100 字的动作、神态或环境细节把这种心情“演”出来。",
           "通过具体动作、神态、语言或心理细节生动展现所选心情，画面具体可感。",
           "写作提示：比如写“着急”可写来回踱步、看表、皱眉；写“开心”可写眉开眼笑、蹦跳欢呼。",
           rubric_keywords=[["手", "脚", "眼", "脸", "眉", "心", "步", "跳", "笑", "抖", "汗"], ["像", "仿佛", "恨不得", "一下子", "不停"]],
           min_chars=50,
           sample_answer="离发车只剩五分钟了，爸爸却还没找到车票！他在背包里飞快地翻找着，额头上渗出了细密的汗珠，眉头拧成了一个大疙瘩。我也急得像热锅上的蚂蚁，在检票口踮着脚尖不停地张望。",
           scaffolds=[
               "开头可用：离约定时间只剩五分钟了…… / 看到奖状的那一刻……",
               "好词锦囊：急得像热锅上的蚂蚁、眉开眼笑、手足无措、心花怒放、屏息凝神",
               "细节支架：写眼神/眉毛的变化 + 手脚的连续动作 + 心里的比喻感受",
           ]),
        _q("g4-c44-6", "G4-C4-4", "reading_choice", "hard",
           "按游览顺序写景物（如《记金华的双龙洞》）时，怎样才能让读者清楚你的游览路线？", "在段首使用清晰的过渡句（如“走完长廊，便来到万寿山脚下”“出了洞口，再往北走”），交代移步换景的过程",
           "移步换景配合清晰的过渡句，能让文章脉络一目了然。",
           options=["东写一句西写一句，不交代位置", "在段首使用清晰的过渡句（如“走完长廊，便来到万寿山脚下”“出了洞口，再往北走”），交代移步换景的过程", "每一段都用相同的第一句话", "不分段"],
           correct_index=1),
    ]

    return bank


def _build_g6_questions() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in CHINESE_G6_NODES}

    # G6-C1-1 小升初高频多音字与易错读音
    bank["G6-C1-1"] = [
        _q("g6-c11-1", "G6-C1-1", "basic_choice", "basic",
           "“参差不齐”中“参差”的正确读音是：", "cēn cī",
           "“参差”表示长短、高低、大小不一致，固定读 cēn cī。",
           options=["cān chā", "cēn cī", "shēn cī", "cān cī"], correct_index=1),
        _q("g6-c11-2", "G6-C1-1", "basic_choice", "basic",
           "“狂风怒号”与“号叫”中的“号”应读作：", "háo",
           "表示拖长声音大声呼叫或风声呼啸时读二声 háo；表示名称、号码时读四声 hào。",
           options=["hào", "háo", "hǎo", "hāo"], correct_index=1),
        _q("g6-c11-3", "G6-C1-1", "basic_choice", "medium",
           "下列加点多音字读音完全相同的一组是：", "蒙古包(měng)  内蒙古(měng)",
           "指蒙古族或内蒙古时均读三声 měng；“欺骗/蒙骗”读 mēng，“蒙昧/迷蒙”读 méng。",
           options=["蒙骗(mēng)  蒙古包(měng)", "蒙古包(měng)  内蒙古(měng)", "单薄(báo)  薄弱(bó)", "倔强(jiàng)  勉强(qiǎng)"],
           correct_index=1),
        _q("g6-c11-4", "G6-C1-1", "basic_choice", "medium",
           "下列小升初高频易误读字中，读音全部正确的一项是：", "正月(zhēng)  提供(gōng)  模样(mú)",
           "农历一月“正月”读一声 zhēng；“提供”读一声 gōng；“模样、模具”读 mú。",
           options=["正月(zhèng)  提供(gòng)  模样(mó)", "正月(zhēng)  提供(gōng)  模样(mú)", "入场券(juàn)  酵母(xiào)  机械(jiè)", "悄然(qiāo)  笨拙(zhuó)  澎湃(bài)"],
           correct_index=1),
        _hanzi_tile_q("g6-c11-5", "G6-C1-1", "medium", "勉强", "miǎn qiǎng", ["免", "僵"],
                      "“勉强”读作 miǎn qiǎng，是小升初高频字音字形考点。", seed=601, audio_text="勉强"),
        _q("g6-c11-6", "G6-C1-1", "dictation_spell", "hard",
           "听录音并结合拼音「lǐng lüè」，用键盘精准写出该词：", "领略",
           "“领略”意为了解事物的情况并体会其意义或趣味。",
           hint="2 个汉字", audio_text="领略", distractors=["令", "掠", "路", "格"]),
    ]

    # G6-C1-2 同音字形近字综合辨析
    bank["G6-C1-2"] = [
        _q("g6-c12-1", "G6-C1-2", "basic_choice", "basic",
           "依次填入“干燥、急____、洗____、鼓____”横线上的形近字，完全正确的是：", "躁、澡、噪",
           "足字旁“急躁”（脾气急得跳脚），三点水“洗澡”（用水洗），口字旁“鼓噪/噪音”（声音嘈杂）。",
           options=["噪、澡、躁", "躁、澡、噪", "澡、躁、噪", "躁、噪、澡"], correct_index=1),
        _hanzi_tile_q("g6-c12-2", "G6-C1-2", "basic", "辉煌", "huī huáng", ["灰", "煌"],
                      "“辉煌”形容光彩夺目或成就卓著。", seed=602, audio_text="辉煌"),
        _q("g6-c12-3", "G6-C1-2", "basic_choice", "medium",
           "下列各组词语中，完全没有错别字的一组是：", "悬崖  陶醉  斩钉截铁  暴露无遗",
           "A 应为“别出心裁”；B 应为“技高一筹”；D 应为“沧海一粟”。",
           options=["悬涯  别出心才  忘乎所以", "陶醉  技高一愁  全神贯注", "悬崖  陶醉  斩钉截铁  暴露无遗", "苍海一粟  威风凛凛  余音绕梁"],
           correct_index=2),
        _hanzi_tile_q("g6-c12-4", "G6-C1-2", "medium", "繁殖", "fán zhí", ["凡", "植"],
                      "“繁殖”的“殖”为歹字旁，“植树”的“植”为木字旁。", seed=603, audio_text="繁殖"),
        _q("g6-c12-5", "G6-C1-2", "basic_choice", "hard",
           "“这首古琴曲如高山流水，令听众____在悠远的意境中。”最恰当的词语是：", "沉醉（或陶醉）",
           "沉浸在优美的艺术意境中用“沉醉”或“陶醉”。",
           options=["沉重", "沉醉（或陶醉）", "昏迷", "迷惑"], correct_index=1),
        _q("g6-c12-6", "G6-C1-2", "dictation_spell", "hard",
           "听录音并结合拼音「fēn fù」，用键盘精准写出该词语：", "吩咐",
           "“吩咐”两字均为口字旁。",
           hint="2 个汉字", audio_text="吩咐", distractors=["份", "付", "纷", "附"]),
    ]

    # G6-C1-3 成语感情色彩与熟语运用
    bank["G6-C1-3"] = [
        _q("g6-c13-1", "G6-C1-3", "basic_choice", "basic",
           "下列源于戏曲或传统艺术的成语中，用来形容“歌声或乐曲极其优美动听，长久留在耳畔”的是：", "余音绕梁（或天籁之音）",
           "“余音绕梁”形容歌声或音乐优美，余音回旋不绝；“科班出身”指受过正规专业训练；“粉墨登场”指化装上台演戏。",
           options=["粉墨登场", "科班出身", "余音绕梁（或天籁之音）", "有板有眼"], correct_index=2),
        _q("g6-c13-2", "G6-C1-3", "basic_choice", "basic",
           "下列四字成语中，感情色彩与其他三项不同（属于贬义词）的一项是：", "忘乎所以",
           "“忘乎所以”指因过度兴奋或骄傲而忘记了一切，含贬义；其余三项均为褒义词。",
           options=["鞠躬尽瘁", "高瞻远瞩", "忘乎所以", "妙笔生花"], correct_index=2),
        _hanzi_tile_q("g6-c13-3", "G6-C1-3", "medium", "安居乐业", "ān jū lè yè", ["按", "夜"],
                      "“安居乐业”常用于描绘社会安定、百姓幸福的景象。", seed=604, audio_text="安居乐业"),
        _q("g6-c13-4", "G6-C1-3", "basic_choice", "medium",
           "下列句子中加点成语使用不恰当的一项是：", "犯罪分子在警察面前斩钉截铁地狡辩着。",
           "“斩钉截铁”形容说话或行动坚决果断、毫不犹豫，多用于褒义，不能形容犯罪分子狡辩。",
           options=["面对敌人的威逼利诱，革命烈士斩钉截铁地拒绝了。", "鲁迅先生笔下的人物个个惟妙惟肖、入木三分。", "犯罪分子在警察面前斩钉截铁地狡辩着。", "故宫博物院里的珍贵文物令人目不暇接。"],
           correct_index=2),
        _q("g6-c13-5", "G6-C1-3", "basic_choice", "hard",
           "“画龙点睛、高山流水、黄钟大吕、巧夺天工”中，专用来赞美“人工技艺极其精巧，胜过天然”的成语是：", "巧夺天工",
           "“巧夺天工”指精巧的人工胜过天然，专用于赞美建筑、雕刻、工艺品等人工造物。",
           options=["画龙点睛", "高山流水", "黄钟大吕", "巧夺天工"], correct_index=3),
        _q("g6-c13-6", "G6-C1-3", "dictation_spell", "hard",
           "听录音并结合拼音「pò bù jí dài」，用键盘精准写出该四字成语：", "迫不及待",
           "“迫不及待”注意是“及”不是“急”。",
           hint="4 个汉字", audio_text="迫不及待", distractors=["急", "带", "破", "代"]),
    ]

    # G6-C1-4 小升初高阶听写与看拼音写词
    bank["G6-C1-4"] = [
        _hanzi_tile_q("g6-c14-1", "G6-C1-4", "basic", "黎明", "lí míng", ["梨", "名"],
                      "“黎明”指天快要亮或刚亮的时候。", seed=605, audio_text="黎明"),
        _hanzi_tile_q("g6-c14-2", "G6-C1-4", "basic", "恩惠", "ēn huì", ["思", "慧"],
                      "“恩惠”两字均为心字底。", seed=606, audio_text="恩惠"),
        _hanzi_tile_q("g6-c14-3", "G6-C1-4", "medium", "平衡", "píng héng", ["评", "恒"],
                      "“平衡”注意“衡”字中间的写法。", seed=607, audio_text="平衡"),
        _q("g6-c14-4", "G6-C1-4", "dictation_spell", "medium",
           "听录音并结合拼音「qīn lüè」，用键盘精准写出该词：", "侵略",
           "“侵略”注意“侵”是单人旁。",
           hint="2 个汉字", audio_text="侵略", distractors=["浸", "掠", "路", "略"]),
        _q("g6-c14-5", "G6-C1-4", "dictation_spell", "hard",
           "听录音并结合拼音「lǎn duò」，用键盘精准写出该词：", "懒惰",
           "“懒惰”两字均为竖心旁，注意“懒”右半部分是“负”不是“贝”。",
           hint="2 个汉字", audio_text="懒惰", distractors=["赖", "随", "堕", "慢"]),
        _q("g6-c14-6", "G6-C1-4", "dictation_spell", "hard",
           "听录音并结合拼音「fán zhí」，用键盘精准写出该词：", "繁殖",
           "“繁殖”注意“殖”为歹字旁。",
           hint="2 个汉字", audio_text="繁殖", distractors=["繁", "植", "值", "直"]),
    ]

    # G6-C2-1 复杂复句与关联词综合
    bank["G6-C2-1"] = [
        _q("g6-c21-1", "G6-C2-1", "sentence_choice", "basic",
           "“我们____要学好课本上的基础知识，____要广泛阅读中外经典名著。”应填入的递进关联词是：", "不仅……还……（或不但……而且……）",
           "后一分句在范围和深度上比前一分句更进一步，属于递进关系。",
           options=["虽然……但是……", "不仅……还……（或不但……而且……）", "与其……不如……", "不是……而是……"],
           correct_index=1),
        _q("g6-c21-2", "G6-C2-1", "sentence_choice", "basic",
           "“地球所拥有的自然资源____无限的，____有限的，因此我们必须精心保护地球。”应填：", "不是……而是……",
           "否定前者（无限的）、肯定后者（有限的），属于并列关系中的否定肯定句式。",
           options=["不是……就是……", "不是……而是……", "既……又……", "哪怕……也……"], correct_index=1),
        _q("g6-c21-3", "G6-C2-1", "sentence_choice", "medium",
           "“____面临怎样的风雪严寒，红军战士____坚定地翻越了夹金山。”应填：", "无论……都……（或不管……总……）",
           "表示无条件关系，在任何艰难条件下结果都不改变。",
           options=["因为……所以……", "无论……都……（或不管……总……）", "只要……就……", "既然……就……"],
           correct_index=1),
        _q("g6-c21-4", "G6-C2-1", "sentence_choice", "medium",
           "“桑娜____自己多受苦受累，____忍心看着西蒙的两个孩子孤苦伶仃地死去。”应填：", "宁可……也不……",
           "在两难境地中宁愿自己吃苦也绝不抛下孤儿，体现桑娜善良淳朴的品格。",
           options=["与其……不如……", "宁可……也不……", "一旦……就……", "即使……也……"], correct_index=1),
        _q("g6-c21-5", "G6-C2-1", "error_spot", "hard",
           "找出下面复句中关联词的语病：「尽管鲁迅先生经常工作到深夜，因此他第二天依然精神饱满地接待青年朋友。」", "关联词搭配不当，“尽管”表转折，后半句应把“因此”改为“但是/可是”",
           "“尽管”引出让步转折，必须与“但是/可是/还是”搭配，不能配因果词“因此”。",
           options=["应该把“尽管”删掉", "关联词搭配不当，“尽管”表转折，后半句应把“因此”改为“但是/可是”", "应该把“经常”删掉", "句子完全正确"],
           correct_index=1),
        _q("g6-c21-6", "G6-C2-1", "sentence_choice", "hard",
           "下列句子中分句间关系判断有误的一项是：", "“与其临渊羡鱼，不如退而结网。”——递进关系",
           "“与其……不如……”是选择（取舍）关系，不是递进关系。",
           options=["“只要我们为人民的利益坚持好的，为人民的利益改正错的，我们这个队伍就一定会兴旺起来。”——条件关系", "“与其临渊羡鱼，不如退而结网。”——递进关系", "“虽然天山这时并不是春天，但是有哪一个春天的花园能比得过这时天山的无边繁花呢？”——转折关系", "“因为狼的本性是凶残的，所以东郭先生差点丧命。”——因果关系"],
           correct_index=1),
    ]

    # G6-C2-2 病句综合诊治（两面对一面/句式杂糅/语序）
    bank["G6-C2-2"] = [
        _q("g6-c22-1", "G6-C2-2", "error_spot", "basic",
           "找出下面小升初高频病句的病因：「能否坚持每天阅读半小时，是提高语文素养的关键。」", "两面对一面（前面有“能否”正反两面，后面“是提高……的关键”只有正面一面）",
           "“能否”包含“能”和“不能”两面，而“提高语文素养”只有正面结果，应删去“能否”。",
           options=["缺少主语", "两面对一面（前面有“能否”正反两面，后面“是提高……的关键”只有正面一面）", "分类不当", "标点错误"],
           correct_index=1),
        _q("g6-c22-2", "G6-C2-2", "error_spot", "basic",
           "找出下面病句的病因：「《少年闰土》这篇课文的作者是鲁迅先生写的。」", "句式杂糅（把“作者是鲁迅先生”和“是鲁迅先生写的”两套句式杂糅在了一起）",
           "保留“作者是鲁迅先生”或“是鲁迅先生写的”其中一种即可。",
           options=["缺少宾语", "句式杂糅（把“作者是鲁迅先生”和“是鲁迅先生写的”两套句式杂糅在了一起）", "否定不当", "前后矛盾"],
           correct_index=1),
        _q("g6-c22-3", "G6-C2-2", "error_spot", "medium",
           "找出下面病句的病因：「为了防止校园欺凌事件不再发生，学校开展了法治安全讲座。」", "否定不当（“防止”与“不再”双重否定导致意思相反，应删去“不”）",
           "“防止/避免/杜绝/忌”本身自带否定意味，后面不能再加“不”。",
           options=["搭配不当", "否定不当（“防止”与“不再”双重否定导致意思相反，应删去“不”）", "语序颠倒", "句式杂糅"],
           correct_index=1),
        _q("g6-c22-4", "G6-C2-2", "error_spot", "medium",
           "找出下面病句的病因：「博物馆展出了两千多年前新出土的一批珍贵青铜器。」", "多项定语语序不当（应改为“展出了新出土的一批两千多年前的珍贵青铜器”）",
           "“两千多年前新出土”听起来像在两千年前出土的，应把“新出土的”放在“两千多年前”前面。",
           options=["缺少主语", "多项定语语序不当（应改为“展出了新出土的一批两千多年前的珍贵青铜器”）", "两面对一面", "概念包含"],
           correct_index=1),
        _q("g6-c22-5", "G6-C2-2", "sentence_choice", "hard",
           "下列句子中完全没有语病的一项是：", "在毕业联欢会上，同学们表演了精彩的相声、合唱和课本剧。",
           "A 两面对一面（有没有/是保证）；B 句式杂糅（本着……为原则）；D 缺主语（通过……使……）。",
           options=["一个人有没有坚强的意志，是事业取得成功的保证。", "本次读书节活动本着培养同学们的阅读习惯为原则。", "在毕业联欢会上，同学们表演了精彩的相声、合唱和课本剧。", "通过六年小学生活，使我们结下了深厚的同窗情谊。"],
           correct_index=2),
        _q("g6-c22-6", "G6-C2-2", "error_spot", "hard",
           "找出下面病句的病因：「小张和小王在路上遇到了，他热情地邀请他星期天去图书馆查资料。」", "指代不明（两个“他”分不清到底是谁邀请谁）",
           "前句出现小张和小王两个人，后句用“他邀请他”造成指代不明，应明确写出人名。",
           options=["缺少谓语", "指代不明（两个“他”分不清到底是谁邀请谁）", "搭配不当", "分类不当"],
           correct_index=1),
    ]

    # G6-C2-3 直述转述与双重否定句转换
    bank["G6-C2-3"] = [
        _q("g6-c23-1", "G6-C2-3", "sentence_choice", "basic",
           "把肯定句“在铁的事实面前，他只好承认了自己的错误”改为双重否定句，最恰当的是：", "在铁的事实面前，他不得不承认了自己的错误。",
           "“只好”对应双重否定词“不得不”，表达别无选择、只能承认的原意。",
           options=["在铁的事实面前，他怎么能承认自己的错误？", "在铁的事实面前，他不得不承认了自己的错误。", "在铁的事实面前，他不可能承认自己的错误。", "在铁的事实面前，他没有承认自己的错误。"],
           correct_index=1),
        _q("g6-c23-2", "G6-C2-3", "sentence_choice", "basic",
           "把“听了老班长的故事，在场的战士都流下了眼泪”改为双重否定句，正确的是：", "听了老班长的故事，在场的战士无不流下眼泪。（或没有一个不流下眼泪）",
           "“都……”改为“无不……”或“没有一个不……”，语气更加深沉强烈。",
           options=["听了老班长的故事，在场的战士难道不流泪吗？", "听了老班长的故事，在场的战士无不流下眼泪。（或没有一个不流下眼泪）", "听了老班长的故事，在场的战士不流下眼泪。", "听了老班长的故事，在场的战士很少不流泪。"],
           correct_index=1),
        _q("g6-c23-3", "G6-C2-3", "sentence_choice", "medium",
           "把直述句“詹天佑经常勉励工作人员说：‘我们的工作首先要精密，不能有一点儿马虎。’”改为转述句，正确的是：", "詹天佑经常勉励工作人员说，他们的工作首先要精密，不能有一点儿马虎。",
           "冒号引号改为逗号，“我们的”改为第三人称“他们的”。",
           options=["詹天佑经常勉励工作人员说，我们的工作首先要精密，不能有一点儿马虎。", "詹天佑经常勉励工作人员说，他们的工作首先要精密，不能有一点儿马虎。", "詹天佑经常勉励工作人员说：“他们的工作首先要精密，不能有一点儿马虎。”", "詹天佑经常勉励工作人员说，他的工作首先要精密。"],
           correct_index=1),
        _q("g6-c23-4", "G6-C2-3", "sentence_choice", "medium",
           "把直述句“老汉冷冷地说：‘可以退党，到我这儿报名。’”改为转述句，正确的是：", "老汉冷冷地说，可以退党，到他那儿报名。",
           "第一人称“我”改为“他”，近指方位“这儿”在转述时改为远指“那儿”。",
           options=["老汉冷冷地说，可以退党，到我这儿报名。", "老汉冷冷地说，可以退党，到他这儿报名。", "老汉冷冷地说，可以退党，到他那儿报名。", "老汉冷冷地说：“可以退党，到他那儿报名。”"],
           correct_index=2),
        _q("g6-c23-5", "G6-C2-3", "sentence_choice", "hard",
           "下列句子中，与其他三句意思完全相反的一句是：", "我们怎能不怀疑这件事的真实性呢？",
           "A/B/C 意思都是“我们相信（不怀疑）”；而“怎能不怀疑”意思是“我们非常怀疑”，三重否定变化需仔细分辨。",
           options=["我们毫不怀疑这件事的真实性。", "我们不能怀疑这件事的真实性。", "我们怎能怀疑这件事的真实性呢？", "我们怎能不怀疑这件事的真实性呢？"],
           correct_index=3),
        _q("g6-c23-6", "G6-C2-3", "sentence_choice", "hard",
           "直述句含祈使语气：“指导员对炊事班长说：‘请把这根鱼钩好好保存起来！’”改为转述句最恰当的是：", "指导员让炊事班长把那根鱼钩好好保存起来。",
           "祈使句转述时，去掉“请”和感叹号，将“对……说”灵活转化为“让/嘱咐……”，指示代词“这”改“那”。",
           options=["指导员对炊事班长说，请把这根鱼钩好好保存起来！", "指导员让炊事班长把那根鱼钩好好保存起来。", "指导员对炊事班长说：“把那根鱼钩保存起来。”", "炊事班长让指导员把那根鱼钩保存起来。"],
           correct_index=1),
    ]

    # G6-C2-4 修辞综合赏析与标点精析
    bank["G6-C2-4"] = [
        _q("g6-c24-1", "G6-C2-4", "sentence_choice", "basic",
           "“我是亲友之间交往的礼品，我是婚礼的冠冕，我是生者赠予死者最后的祭献。”（纪伯伦《花之歌》）主要运用了哪些修辞手法？", "排比和暗喻（比喻）",
           "三个“我是……”构成排比，同时以花朵的口吻把花比作礼品、冠冕、祭献，兼用暗喻与拟人。",
           options=["夸张和反问", "排比和暗喻（比喻）", "设问和对比", "借代和反语"], correct_index=1),
        _q("g6-c24-2", "G6-C2-4", "sentence_choice", "basic",
           "下列句子中分号（；）使用正确的一项是：", "潮水涨来时，我拥抱着他；潮水退去时，我扑倒在他脚下。",
           "两个结构对称、意义并列且内部已有逗号的分句之间，应使用分号隔开。",
           options=["我喜欢读《西游记》；《三国演义》和《水浒传》。", "潮水涨来时，我拥抱着他；潮水退去时，我扑倒在他脚下。", "今天天气真好；我们一起去踢球吧。", "妈妈问我；“作业写完了吗？”"],
           correct_index=1),
        _q("g6-c24-3", "G6-C2-4", "sentence_choice", "medium",
           "“走了许久，远远地望见了一条迂回的明如玻璃的带子——河！”句中破折号（——）的作用是：", "表示解释说明（点明“明如玻璃的带子”就是远处的河）",
           "破折号引出对前文“明如玻璃的带子”的直接解释说明。",
           options=["表示声音的延长", "表示解释说明（点明“明如玻璃的带子”就是远处的河）", "表示话题突然转换", "表示说话断断续续"],
           correct_index=1),
        _q("g6-c24-4", "G6-C2-4", "sentence_choice", "medium",
           "“古老的钟发哑地敲了十下，十一下……始终不见丈夫回来。”（《穷人》）句中省略号（……）的作用是：", "表示钟声断断续续及桑娜等待丈夫时度日如年的焦急心理",
           "这里的省略号既写钟声一下又一下敲响的延续，更折射出桑娜内心的煎熬与担忧。",
           options=["表示列举同类事物省略", "表示钟声断断续续及桑娜等待丈夫时度日如年的焦急心理", "表示引用原文省略", "表示桑娜睡着了"],
           correct_index=1),
        _q("g6-c24-5", "G6-C2-4", "sentence_choice", "hard",
           "“五岭逶迤腾细浪，乌蒙磅礴走泥丸”这两句诗同时运用了哪些修辞手法？", "对偶、夸张、比喻（把绵延五岭比作细浪，把高大乌蒙山比作滚动的泥丸）",
           "先用“逶迤”“磅礴”极言山高险峻，再以“细浪”“泥丸”比喻夸张将其缩小，凸显红军藐视困难的英雄气概，且上下句严格对偶。",
           options=["只用了拟人", "对偶、夸张、比喻（把绵延五岭比作细浪，把高大乌蒙山比作滚动的泥丸）", "设问和反问", "反复和引用"],
           correct_index=1),
        _q("g6-c24-6", "G6-C2-4", "sentence_choice", "hard",
           "下列句子中引号作用判断完全正确的一项是：「①“腊七腊八，冻死寒鸦”，这是一年里最冷的时候。②像他这样“聪明”地抄作业，只会害了自己。」", "①表示直接引用谚语；②表示反语讽刺",
           "①直接引用民间谚语；②“聪明”是正话反说，讽刺抄作业的自欺欺人。",
           options=["①表示特定称谓；②表示直接引用", "①表示直接引用谚语；②表示反语讽刺", "①和②都表示特殊含义", "①表示讽刺；②表示强调"],
           correct_index=1),
    ]

    # G6-C3-1 写景咏物名篇（《宿建德江》《六月二十七日望湖楼醉书》《石灰吟》《竹石》）
    bank["G6-C3-1"] = [
        _poem_tile_q("g6-c31-1", "G6-C3-1", "basic",
                     "点选字块，补全孟浩然《宿建德江》名句：「野旷天低树，____。」",
                     "江清月近人", ["青", "进"],
                     "原野空旷使得天幕比远树还低，江水清澈更觉明月与人亲近。", seed=631),
        _poem_tile_q("g6-c31-2", "G6-C3-1", "basic",
                     "点选字块，补全于谦《石灰吟》托物言志名句：「粉骨碎身浑不怕，____。」",
                     "要留清白在人间", ["青", "闲"],
                     "借石灰经烈火焚烧而留清白于世，抒发诗人坚贞不屈、洁身自好的高尚节操。", seed=632),
        _q("g6-c31-3", "G6-C3-1", "reading_choice", "medium",
           "苏轼《六月二十七日望湖楼醉书》“黑云翻墨未遮山，白雨跳珠乱入船”中，诗人分别把乌云和骤雨比作了什么？", "把翻滚的乌云比作打翻的黑墨水，把倾盆大雨的雨点比作跳动的白珍珠",
           "“翻墨”状乌云来势凶猛，“跳珠”写雨点大而急促，动感极强。",
           options=["把乌云比作大山，把白雨比作小船", "把翻滚的乌云比作打翻的黑墨水，把倾盆大雨的雨点比作跳动的白珍珠", "把西湖比作墨水池", "把小船比作珍珠"],
           correct_index=1),
        _q("g6-c31-4", "G6-C3-1", "reading_choice", "medium",
           "郑燮《竹石》“千磨万击还坚劲，任尔东西南北风”与于谦《石灰吟》在写法上的共同点是：", "都运用了“托物言志”的手法，借所咏之物表达自己坚贞不屈的高尚气节",
           "《竹石》借岩竹言坚韧刚正之志，《石灰吟》借石灰言清白坚贞之节，均为托物言志典范。",
           options=["都只是单纯介绍植物和矿物的科学属性", "都运用了“托物言志”的手法，借所咏之物表达自己坚贞不屈的高尚气节", "都表达了思念家乡的哀愁", "都描写了冬天下雪的景色"],
           correct_index=1),
        _q("g6-c31-5", "G6-C3-1", "poem_fill", "hard",
           "精准默写于谦《石灰吟》末句：「粉骨碎身浑不怕，________。」",
           "要留清白在人间",
           "“清白”既指石灰的颜色，更双关诗人高洁清廉的品格。",
           hint="7 个汉字，出自《石灰吟》", distractors=["青", "留", "流", "闲"]),
        _q("g6-c31-6", "G6-C3-1", "poem_fill", "hard",
           "精准默写郑燮《竹石》末句：「千磨万击还坚劲，________。」",
           "任尔东西南北风",
           "“任尔”意为任凭你，表现对恶劣环境的蔑视与顽强抗争。",
           hint="7 个汉字，出自《竹石》", distractors=["凭", "你", "耳", "丰"]),
    ]

    # G6-C3-2 家国情怀与宋词元曲（《西江月·夜行黄沙道中》《过故人庄》《七律·长征》）
    bank["G6-C3-2"] = [
        _poem_tile_q("g6-c32-1", "G6-C3-2", "basic",
                     "点选字块，补全辛弃疾《西江月·夜行黄沙道中》名句：「稻花香里说丰年，____。」",
                     "听取蛙声一片", ["清", "池"],
                     "从嗅觉（稻花香）到听觉（蛙声一片），洋溢着丰收在望的喜悦。", seed=633),
        _poem_tile_q("g6-c32-2", "G6-C3-2", "basic",
                     "点选字块，补全孟浩然《过故人庄》名句：「待到重阳日，____。」",
                     "还来就菊花", ["在", "酒"],
                     "不待主人相邀便主动约定重阳节再来赏菊饮酒，可见主客之间情谊深厚真挚。", seed=634),
        _q("g6-c32-3", "G6-C3-2", "reading_choice", "medium",
           "《西江月·夜行黄沙道中》中，“西江月”和“夜行黄沙道中”分别是什么？", "“西江月”是词牌名，“夜行黄沙道中”是词的题目",
           "宋词通常由词牌名（决定格律字数）和题目（决定内容）组成。",
           options=["两个都是词牌名", "“西江月”是词牌名，“夜行黄沙道中”是词的题目", "“西江月”是题目，“夜行黄沙道中”是作者", "这是一首五言律诗"],
           correct_index=1),
        _q("g6-c32-4", "G6-C3-2", "reading_choice", "medium",
           "《七律·长征》“金沙水拍云崖暖，大渡桥横铁索寒”中，“暖”与“寒”两个字分别蕴含了怎样的情感与历史背景？", "“暖”写巧渡金沙江的欢快喜悦，“寒”写强渡大渡河、飞夺泸定桥的惊险悲壮",
           "一暖一寒鲜明对比，既写实景体感，更浓缩了两次战役截然不同的心理体验。",
           options=["只是说明金沙江在夏天、大渡河在冬天", "“暖”写巧渡金沙江的欢快喜悦，“寒”写强渡大渡河、飞夺泸定桥的惊险悲壮", "说明红军战士带了棉衣", "没有特殊含义"],
           correct_index=1),
        _q("g6-c32-5", "G6-C3-2", "poem_fill", "hard",
           "精准默写《七律·长征》首联下句：「红军不怕远征难，________。」",
           "万水千山只等闲",
           "“只等闲”意为只当成平平常常的事，总领全诗。",
           hint="7 个汉字，出自《七律·长征》", distractors=["千", "万", "止", "间"]),
        _q("g6-c32-6", "G6-C3-2", "poem_fill", "hard",
           "精准默写孟浩然《过故人庄》颔联下句：「绿树村边合，________。」",
           "青山郭外斜",
           "近处绿树环绕村庄，远处青山在城郭外依势倾斜，对仗工整。",
           hint="5 个汉字，出自《过故人庄》", distractors=["清", "城", "郊", "邪"]),
    ]

    # G6-C3-3 经典文言文（《伯牙鼓琴》《书戴嵩画牛》《学弈》《两小儿辩日》）
    bank["G6-C3-3"] = [
        _q("g6-c33-1", "G6-C3-3", "reading_choice", "basic",
           "《伯牙鼓琴》“方鼓琴而志在太山，锺子期曰：‘善哉乎鼓琴，巍巍乎若太山！’”中，“志”和“善哉”的意思分别是：", "心志、情志；好啊",
           "“志在太山”指心里想到高山；“善哉”是赞叹词“好啊！”。",
           options=["志向；善良的人", "心志、情志；好啊", "记号；擅长", "杂志；再见"], correct_index=1),
        _q("g6-c33-2", "G6-C3-3", "reading_choice", "basic",
           "锺子期死后，伯牙“破琴绝弦，终身不复鼓琴”，由此流传下来的千古成语是：", "高山流水（或知音难觅）",
           "后人用“高山流水”或“知音”比喻真正了解自己心意的朋友或乐曲高妙。",
           options=["画蛇添足", "高山流水（或知音难觅）", "滥竽充数", "叶公好龙"], correct_index=1),
        _q("g6-c33-3", "G6-C3-3", "reading_choice", "medium",
           "《学弈》“虽与之俱学，弗若之矣。为是其智弗若与？曰：非然也”告诉我们的核心道理是：", "学习成败的关键在于是否专心致志，而不是天资聪明与否",
           "两人同拜弈秋为师，一人专心致志，一人三心二意，结果大不相同。",
           options=["下围棋非常难学", "学习成败的关键在于是否专心致志，而不是天资聪明与否", "天鹅比围棋更重要", "老师教得不够好"],
           correct_index=1),
        _q("g6-c33-4", "G6-C3-3", "reading_choice", "medium",
           "《书戴嵩画牛》中牧童指出名画家戴嵩《斗牛图》的错误（“牛斗，力在角，尾搐入两股间，今乃掉尾而斗，谬矣”），苏轼借此在结尾点明的道理是：", "耕当问奴，织当问婢（艺术创作与认识事物要向富有实践经验的劳动者请教，尊重事实）",
           "任何权威都可能出错，实践出真知，向行家请教才不会脱离实际。",
           options=["画家都不懂画牛", "耕当问奴，织当问婢（艺术创作与认识事物要向富有实践经验的劳动者请教，尊重事实）", "牧童比大画家更会画画", "不要收藏名画"],
           correct_index=1),
        _q("g6-c33-5", "G6-C3-3", "reading_choice", "hard",
           "《两小儿辩日》中“孔子不能决也。两小儿笑曰：‘孰为汝多知乎？’”体现了两小儿和孔子怎样的特点？", "两小儿善于观察生活、敢于独立思考质疑；孔子实事求是、谦虚谨慎（知之为知之，不知为不知）",
           "两小儿从视觉大小与触觉冷热两角度大胆论证；孔子不强不知以为知，坦然承认“不能决”。",
           options=["孔子学问太浅，不如小孩子", "两小儿善于观察生活、敢于独立思考质疑；孔子实事求是、谦虚谨慎（知之为知之，不知为不知）", "太阳早上真的比中午更近", "两小儿非常没有礼貌"],
           correct_index=1),
        _q("g6-c33-6", "G6-C3-3", "poem_fill", "hard",
           "听录音或根据提示，精准默写《论语》中关于实事求是学习态度的名句（下句）：「知之为知之，不知为不知，________。」",
           "是知也",
           "“是知也”中第二个“知”通“智”，意为这才是真正的智慧。",
           hint="3 个汉字", audio_text="知之为知之，不知为不知，是知也。", audio_voice="zh-CN-YunxiNeural", distractors=["智", "之", "道", "也"]),
    ]

    # G6-C3-4 传统文化常识与名联警句
    bank["G6-C3-4"] = [
        _poem_tile_q("g6-c34-1", "G6-C3-4", "basic",
                     "点选字块，补全鲁迅《答客诮》名句：「无情未必真豪杰，____。」",
                     "怜子如何不丈夫", ["莲", "夫"],
                     "对子女充满深情怜爱的人，难道就不算真正的英雄大丈夫吗？", seed=635),
        _q("g6-c34-2", "G6-C3-4", "reading_choice", "basic",
           "我国传统文化中被称为“五行”和“五音”的分别是：", "五行：金、木、水、火、土；五音：宫、商、角、徵、羽",
           "小升初文化常识必考：五谷（稻黍稷麦菽）、五行（金木水火土）、五音（宫商角徵羽）、五彩（黄青赤白黑）。",
           options=["五行：东南西北中；五音：哆来咪发索", "五行：金、木、水、火、土；五音：宫、商、角、徵、羽", "五行：仁义礼智信；五音：琴棋书画诗", "五行：稻黍稷麦菽；五音：金石丝竹土"],
           correct_index=1),
        _q("g6-c34-3", "G6-C3-4", "reading_choice", "medium",
           "下列爱国名言与作者对应完全正确的一项是：", "“捐躯赴国难，视死忽如归。”——曹植  /  “位卑未敢忘忧国。”——陆游",
           "曹植《白马篇》“捐躯赴国难，视死忽如归”；陆游《病起书怀》“位卑未敢忘忧国”；李纲“祖宗疆土，当以死守”。",
           options=["“捐躯赴国难，视死忽如归。”——李白", "“捐躯赴国难，视死忽如归。”——曹植  /  “位卑未敢忘忧国。”——陆游", "“位卑未敢忘忧国。”——苏轼", "“天下兴亡，匹夫有责。”——孔子"],
           correct_index=1),
        _q("g6-c34-4", "G6-C3-4", "reading_choice", "medium",
           "《易经》名句“穷则变，变则通，通则久”常用来说明什么道理？", "事物发展到极点或陷入困境时就要变革创新，变革才能通达，通达才能长久发展",
           "强调因时而变、勇于改革创新的哲学智慧。",
           options=["人穷了就要搬家", "事物发展到极点或陷入困境时就要变革创新，变革才能通达，通达才能长久发展", "走路要走通畅的大路", "做事情不要改变最初的方法"],
           correct_index=1),
        _q("g6-c34-5", "G6-C3-4", "poem_fill", "hard",
           "精准默写陆游《病起书怀》中表达即使地位低微也从不敢忘记忧念国事的七字名句：「________。」",
           "位卑未敢忘忧国",
           "“位卑未敢忘忧国”是小升初爱国主题必考名句。",
           hint="7 个汉字，陆游名句", distractors=["碑", "末", "优", "家"]),
        _q("g6-c34-6", "G6-C3-4", "poem_fill", "hard",
           "精准默写曹植《白马篇》爱国名句下句：「捐躯赴国难，________。」",
           "视死忽如归",
           "抱着为国献身的决心奔赴国难，把死亡看得像回家一样从容。",
           hint="5 个汉字，曹植名句", distractors=["是", "乎", "回", "家"]),
    ]

    # G6-C4-1 点面结合与环境描写作用
    p_g6_scene = (
        "黎明的时候，雨突然大了。像泼。像倒。山洪咆哮着，像一群受惊的野马，从山谷里狂奔而来，势不可当。"
        "近一米高的洪水已经在路面上跳舞了。死亡在洪水的狞笑声中逼近。"
        "人们翻身下床，却一脚踩进水里。是谁惊慌地喊了一嗓子，一百多号人你拥我挤地往南跑。"
        "但木桥前，全村人都拥了过来。老汉清瘦的脸上淌着雨水。他不说话，盯着乱哄哄的人们。他像一座山。"
    )
    bank["G6-C4-1"] = [
        _q("g6-c41-1", "G6-C4-1", "reading_choice", "basic",
           "选段第一段集中描写了“暴雨和山洪的凶猛”，这段环境描写在小说《桥》中的主要作用是：", "渲染紧张危急的气氛，推动故事情节发展，反衬老支书临危不惧的高大形象",
           "小说中恶劣的自然环境既交代危机背景、渲染气氛，又为烘托英雄人物做铺垫。",
           options=["单纯介绍当地的气候特征", "渲染紧张危急的气氛，推动故事情节发展，反衬老支书临危不惧的高大形象", "说明木桥修建的位置不好", "凑字数延长篇幅"],
           correct_index=1, passage=p_g6_scene),
        _q("g6-c41-2", "G6-C4-1", "reading_choice", "basic",
           "选段中哪部分是“面”的描写，哪部分是“点”的描写？", "“一百多号人你拥我挤、乱哄哄的人们”是群像（面），“老汉清瘦的脸上淌着雨水……他像一座山”是个体特写（点）",
           "“点面结合”既写出人群慌乱的整体场面（面），又聚焦老汉镇定如山的特写（点），形成强烈对比。",
           options=["全部都是“点”的描写", "“一百多号人你拥我挤、乱哄哄的人们”是群像（面），“老汉清瘦的脸上淌着雨水……他像一座山”是个体特写（点）", "洪水是“点”，雨水是“面”", "全部都是“面”的描写"],
           correct_index=1, passage=p_g6_scene),
        _q("g6-c41-3", "G6-C4-1", "reading_choice", "medium",
           "“近一米高的洪水已经在路面上跳舞了。死亡在洪水的狞笑声中逼近。”这里用“跳舞”“狞笑”写洪水有什么表达效果？", "运用拟人手法，赋予洪水魔鬼般的狰狞姿态，突出形势万分危急",
           "“跳舞”“狞笑”并非写欢快，而是拟人化地写出洪水的肆虐张狂与冷酷无情。",
           options=["说明洪水非常优美欢快", "运用拟人手法，赋予洪水魔鬼般的狰狞姿态，突出形势万分危急", "说明村民们在雨中跳舞", "用词不当"],
           correct_index=1, passage=p_g6_scene),
        _q("g6-c41-4", "G6-C4-1", "reading_choice", "medium",
           "选段多用极短的句子（如“像泼。像倒。”“他像一座山。”），这样写有什么独特效果？", "节奏急促有力，既烘托出洪水袭来时的千钧一发，又凸显老汉坚定果断的气度",
           "短句节奏明快紧迫，极富感染力与视觉冲击力。",
           options=["作者不会写长句子", "节奏急促有力，既烘托出洪水袭来时的千钧一发，又凸显老汉坚定果断的气度", "为了让画面显得悠闲缓慢", "没有任何作用"],
           correct_index=1, passage=p_g6_scene),
        _q("g6-c41-5", "G6-C4-1", "reading_short", "hard",
           "【阅读简答】结合选段，说说作者为什么写“一百多号人你拥我挤地往南跑”，紧接着又写“老汉不说话，盯着乱哄哄的人们。他像一座山”？这样写有什么作用？",
           "运用点面结合与对比手法，用村民们惊慌失措的群像（面）反衬出老支书（点）在危难面前临危不乱、镇定如山、成为乡亲们主心骨的光辉形象。",
           "答题模板：手法（点面结合/对比反衬）+ 内容（村民慌乱与老汉镇定对比）+ 人物形象（临危不惧、主心骨）。",
           passage=p_g6_scene,
           rubric_keywords=[["对比", "反衬", "衬托", "点面"], ["惊慌", "慌乱", "镇定", "沉着", "冷静", "不惧"], ["山", "依靠", "主心骨", "高大", "支书"]],
           min_chars=18,
           sample_answer="运用了点面结合和对比衬托的手法。用村民们惊慌失措、你拥我挤的慌乱场面，反衬出老汉在生死关头沉着镇定、临危不惧，像大山一样成为全村人主心骨的高大形象。",
           scaffolds=[
               "开头可用：这里运用了点面结合与对比反衬的写作手法……",
               "对比分析：以村民们“你拥我挤、乱哄哄”的惊慌群像，反衬老汉“像一座山”的沉着镇定",
               "人物点题：突出了老支书在危难关头临危不惧、作为群众主心骨的崇高形象。",
           ]),
        _q("g6-c41-6", "G6-C4-1", "reading_choice", "hard",
           "在描写大型活动（如运动会开幕式、阅兵式、文艺汇演）时，运用“点面结合”的核心好处是：", "既有整体宏大热烈的气氛（面），又有典型人物生动感人的细节特写（点），层次分明、立体感强",
           "有面无点则空洞，有点无面则单薄，点面结合才能既有气势又有细节。",
           options=["可以少写一半字数", "既有整体宏大热烈的气氛（面），又有典型人物生动感人的细节特写（点），层次分明、立体感强", "不需要写任何人物动作", "只需要抄写活动通知"],
           correct_index=1),
    ]

    # G6-C4-2 小说人物形象与文章主旨提炼
    p_g6_novel = (
        "渔夫皱起眉，他的脸变得严肃、忧虑。“嗯，是个问题！”他搔搔后脑勺说，“嗯，你看怎么办？得把他们抱来，同死人呆在一起怎么行！"
        "哦，我们，我们总能熬过去的！快去！别等他们醒来。”"
        "但桑娜坐着一动不动。"
        "“你怎么啦？不愿意吗？你怎么啦，桑娜？”"
        "“你瞧，他们在这里啦。”桑娜拉开了帐子。"
    )
    bank["G6-C4-2"] = [
        _q("g6-c42-1", "G6-C4-2", "reading_choice", "basic",
           "选段中渔夫说“我们，我们总能熬过去的！”，一个“熬”字最深刻地体现了：", "渔夫清楚收养两个孤儿会让原本贫苦的生活更加艰难，但他依然宁愿自己受苦也要拯救孩子的善良与担当",
           "“熬”字既写出了穷人日子的煎熬艰辛，更映照出渔夫质朴坚韧、舍己为人的高尚灵魂。",
           options=["渔夫正在家里熬鱼汤", "渔夫清楚收养两个孤儿会让原本贫苦的生活更加艰难，但他依然宁愿自己受苦也要拯救孩子的善良与担当", "渔夫觉得生活非常轻松愉快", "渔夫不想收养孩子"],
           correct_index=1, passage=p_g6_novel),
        _q("g6-c42-2", "G6-C4-2", "reading_choice", "basic",
           "当渔夫催促桑娜快去抱孩子时，“但桑娜坐着一动不动”，是因为：", "桑娜早就已经把两个孤儿抱回来了，听到丈夫和自己心意相通，内心百感交集、如释重负",
           "桑娜此前一直忐忑不安怕丈夫责怪，此刻听到丈夫主动提出抱孩子，感动与欣慰交织。",
           options=["桑娜不愿意去抱孩子", "桑娜早就已经把两个孤儿抱回来了，听到丈夫和自己心意相通，内心百感交集、如释重负", "桑娜腿麻了站不起来", "桑娜没有听清渔夫的话"],
           correct_index=1, passage=p_g6_novel),
        _q("g6-c42-3", "G6-C4-2", "reading_choice", "medium",
           "小说在“桑娜拉开了帐子”处戛然而止，这种留白式的结尾有什么妙处？", "一切尽在不言中，夫妻俩善良的心灵在此刻完全契合，给读者留下无限感动与回味的空间",
           "悬念解开、心灵共鸣达成，此时收束全篇余音袅袅、耐人寻味。",
           options=["作者忘记写后面的故事了", "一切尽在不言中，夫妻俩善良的心灵在此刻完全契合，给读者留下无限感动与回味的空间", "说明故事还没有写完", "为了让读者猜帐子里有什么"],
           correct_index=1, passage=p_g6_novel),
        _q("g6-c42-4", "G6-C4-2", "reading_choice", "medium",
           "列夫·托尔斯泰这篇小说题目叫《穷人》，通篇却没有出现一个“穷”字，而是处处展现他们：", "物质生活虽然极度贫穷，但精神世界和道德品质却无比富足高尚",
           "物质之“穷”与精神之“富”形成强烈张力，深化了小说赞美人性光辉的主旨。",
           options=["其实家里非常有钱", "物质生活虽然极度贫穷，但精神世界和道德品质却无比富足高尚", "一点也不善良", "每天都去打鱼卖钱"],
           correct_index=1, passage=p_g6_novel),
        _q("g6-c42-5", "G6-C4-2", "reading_short", "hard",
           "【阅读简答】读完选段，请结合渔夫的神态和语言，简要分析渔夫是一个怎样的人，以及小说表达了怎样的主题思想。",
           "渔夫虽然生活贫苦，但听说邻居西蒙死后立刻决定把孤儿抱来抚养，甘愿自己“熬”过苦日子，可见他心地善良、淳朴有担当、宁可自己吃苦也要帮助他人。小说赞美了穷人虽物质贫乏却精神高尚的美好人性。",
           "答题思路：结合言行（皱眉忧虑、主动要抱孩子、“总能熬过去”）+ 人物性格（善良、有担当、舍己为人）+ 文章主旨（赞美穷人高尚富足的精神品质）。",
           passage=p_g6_novel,
           rubric_keywords=[["熬", "抱来", "抚养", "收养"], ["善良", "淳朴", "担当", "舍己为人", "关心", "高尚", "美好"]],
           min_chars=18,
           sample_answer="从渔夫“得把他们抱来”“我们总能熬过去的”等语言中，可以看出他是一个心地善良、勇于担当、宁愿自己吃苦也要帮助他人的好人。文章赞美了穷人物质虽穷但心灵高尚富足的美好品格。",
           scaffolds=[
               "人物形象：从渔夫“得把他们抱来”“总能熬过去的”等言行中，看出他是一个……的人",
               "好词锦囊：心地善良、淳朴坚韧、勇于担当、舍己为人、人性光辉",
               "主旨提炼：文章通过写桑娜夫妇收养孤儿，赞美了穷人物质虽贫乏但精神无比高尚的美好品质。",
           ]),
        _q("g6-c42-6", "G6-C4-2", "reading_choice", "hard",
           "小升初阅读小说时，我们应该从哪三个核心要素去把握文章主旨与人物形象？", "环境描写、故事情节（开端/发展/高潮/结局）、人物塑造（言行心理细节）",
           "小说三要素是人物、情节、环境，三者共同服务于主题思想的表达。",
           options=["字数、页码、出版社", "环境描写、故事情节（开端/发展/高潮/结局）、人物塑造（言行心理细节）", "只看标题和第一句话", "只统计文中有几个成语"],
           correct_index=1),
    ]

    # G6-C4-3 非连续性文本与多材料整合
    p_g6_multi = (
        "【材料一】故宫太和殿俗称“金銮殿”，高 35.05 米，面积 2377 平方米，共 55 间，是我国现存最大的木结构大殿。"
        "【材料二】参观须知：故宫博物院实行自南向北单向参观路线，观众一律从午门（南门）进入，参观结束后由神武门（北门）或东华门离开。周一闭馆（法定节假日除外）。"
        "【材料三】小明一家想在下周二上午用 1.5 小时重点游览故宫中轴线上的“前三殿”（太和殿、中和殿、保和殿），并拍下太和殿全景照。"
    )
    bank["G6-C4-3"] = [
        _q("g6-c43-1", "G6-C4-3", "reading_choice", "basic",
           "阅读非连续性文本时，要回答“小明一家应该从哪个门进故宫、周几不能去”，我们应该重点提取哪则材料的信息？", "【材料二】参观须知（从午门进入，周一闭馆）",
           "带有明确阅读目的时，应快速定位与之直接相关的材料段落（有目的地阅读）。",
           options=["【材料一】太和殿建筑数据", "【材料二】参观须知（从午门进入，周一闭馆）", "不需要看任何材料", "去查字典"],
           correct_index=1, passage=p_g6_multi),
        _q("g6-c43-2", "G6-C4-3", "reading_choice", "basic",
           "根据【材料一】和【材料二】，下列说法完全符合原文的一项是：", "太和殿是我国现存最大的木结构大殿，小明一家下周二可以从南边的午门进院参观",
           "太和殿是现存最大木结构大殿，周二正常开馆，从午门（南门）进入。",
           options=["观众可以从神武门（北门）进入故宫，从午门离开", "太和殿是我国现存最大的木结构大殿，小明一家下周二可以从南边的午门进院参观", "非节假日的周一故宫全天开放", "太和殿一共有 35 间房"],
           correct_index=1, passage=p_g6_multi),
        _q("g6-c43-3", "G6-C4-3", "reading_choice", "medium",
           "【材料一】介绍太和殿时主要运用了什么说明方法？有什么作用？", "列数字；通过精准的数据具体、准确地突出了太和殿高大宏伟、规模居首的特点",
           "35.05 米、2377 平方米、55 间均为精确列数字，体现说明文语言的科学严谨。",
           options=["打比方；写出了太和殿像一朵花", "列数字；通过精准的数据具体、准确地突出了太和殿高大宏伟、规模居首的特点", "作诠释；解释了什么是木头", "下定义"],
           correct_index=1, passage=p_g6_multi),
        _q("g6-c43-4", "G6-C4-3", "reading_choice", "medium",
           "“有目的地阅读”同一篇文章时，如果两个人的阅读目的不同（如一人想做导游词，一人想研究古建筑结构），他们应该：", "根据各自的阅读任务筛选相关材料重点精读，与目的无关的内容快速浏览或略读",
           "六年级核心阅读策略：根据阅读目的灵活选用精读、略读、跳读等方法。",
           options=["两个人都必须逐字逐句背诵全文", "根据各自的阅读任务筛选相关材料重点精读，与目的无关的内容快速浏览或略读", "都不看正文只看页码", "只读最后一行"],
           correct_index=1, passage=p_g6_multi),
        _q("g6-c43-5", "G6-C4-3", "reading_short", "hard",
           "【阅读简答】请综合三则材料，为小明一家拟定一条下周二上午游览故宫的简明路线与提示（需包含：进出城门、重点游览建筑及太和殿的一个亮点）。",
           "下周二上午从南门（午门）进入故宫，沿中轴线自南向北重点游览太和殿（我国现存最大的木结构大殿，可在此拍全景照）、中和殿和保和殿，游览结束后从北门（神武门）或东华门离开。",
           "整合思路：时间（周二正常开馆）+ 入口（午门进）+ 核心景点与亮点（太和殿/现存最大木结构大殿、中和殿、保和殿）+ 出口（神武门或东华门出）。",
           passage=p_g6_multi,
           rubric_keywords=[["午门"], ["太和殿", "最大", "木结构", "中轴线", "前三殿"], ["神武门", "东华门", "北", "离开", "出"]],
           min_chars=18,
           sample_answer="下周二上午从南边的午门进入故宫，沿中轴线自南向北依次游览太和殿（我国现存最大的木结构大殿，可拍全景照）、中和殿和保和殿，最后从北边的神武门或东华门离开。",
           scaffolds=[
               "路线框架：下周二上午从______（南门）进入 → 沿中轴线游览______ → 从______离开",
               "景点亮点：重点在太和殿（我国现存最大的木结构大殿）拍摄全景照",
               "注意事项：故宫实行自南向北单向参观，周二正常开馆。",
           ]),
        _q("g6-c43-6", "G6-C4-3", "reading_choice", "hard",
           "如果小明把行程改在“普通周一下午，从神武门进院参观太和殿”，这个计划有几处行不通？", "两处行不通：①普通周一故宫闭馆；②神武门只出不进，必须从午门进入",
           "对照材料二，周一闭馆且实行自南向北单向通行（午门进、神武门出）。",
           options=["完全可行，没有任何问题", "只有一处行不通", "两处行不通：①普通周一故宫闭馆；②神武门只出不进，必须从午门进入", "太和殿已经被拆除了"],
           correct_index=2, passage=p_g6_multi),
    ]

    # G6-C4-4 小升初审题立意与100字高分微写作
    bank["G6-C4-4"] = [
        _q("g6-c44-1", "G6-C4-4", "reading_choice", "basic",
           "小升初作文题《围绕中心意思写》（如围绕“暖”“甜”“悔”“迷”一个字写作文），高分构思的关键是：", "从不同方面或精选 1～2 个最典型的生活镜头，层层深入地紧扣这个中心字展开，详略得当",
           "围绕中心意思选材，既可以从不同方面并列展开，也可以把一件事写深写透。",
           options=["在文章里把这个字抄写五十遍", "从不同方面或精选 1～2 个最典型的生活镜头，层层深入地紧扣这个中心字展开，详略得当", "前半篇写“甜”，后半篇改写“苦”，没有中心", "只写名言警句不写事例"],
           correct_index=1),
        _q("g6-c44-2", "G6-C4-4", "reading_choice", "basic",
           "在《让真情自然流露》习作中，“融情于景”是一种高级表达技巧。当你想表达“考试失利或与好友分别时的失落难过”时，下面哪段景物描写最贴切？", "天色阴沉沉的，秋风卷起几片枯黄的梧桐叶在空荡荡的小路上打着旋儿，连路灯的光也显得冷清清的。",
           "一切景语皆情语，阴沉的天色、枯叶、冷清的路灯自然映衬出内心的孤单与失落。",
           options=["阳光明媚，小鸟在枝头欢快地唱着迎宾曲，花儿朝我微微笑。", "天色阴沉沉的，秋风卷起几片枯黄的梧桐叶在空荡荡的小路上打着旋儿，连路灯的光也显得冷清清的。", "今天的气温是摄氏二十度，东南风三级。", "操场上到处都是欢声笑语，热闹非凡。"],
           correct_index=1),
        _q("g6-c44-3", "G6-C4-4", "reading_choice", "medium",
           "小升初常见半命题作文《那一刻，我长大了》《有你，真好》，审题时最重要的抓手是：", "抓住题眼“那一刻”（定格触动心灵的具体瞬间细节）与“真好”（用第二人称“你”倾诉真挚情感）",
           "扣住“那一刻”做慢镜头特写，扣住“你”用第二人称对话抒情，是半命题夺高分的关键。",
           options=["随便换掉题目不按原题写", "抓住题眼“那一刻”（定格触动心灵的具体瞬间细节）与“真好”（用第二人称“你”倾诉真挚情感）", "从一岁出生写到十二岁毕业的流水账", "全篇用第三人称写一个陌生人"],
           correct_index=1),
        _q("g6-c44-4", "G6-C4-4", "reading_choice", "medium",
           "写毕业季赠言或《难忘小学生活》开头结尾时，怎样才能避免俗套、脱颖而出？", "截取教室黑板倒计时、操场梧桐树或同桌借橡皮等充满母校烟火气的典型细节，运用排比或首尾呼应升华同窗情、师生恩",
           "以小见大、由专属母校细节切入，辅以修辞与首尾呼应，最能打动阅卷老师。",
           options=["背诵一篇网上的万能套话模板", "截取教室黑板倒计时、操场梧桐树或同桌借橡皮等充满母校烟火气的典型细节，运用排比或首尾呼应升华同窗情、师生恩", "只写“光阴似箭，日月如梭，写完了”", "罗列全班五十个同学的学号"],
           correct_index=1),
        _q("g6-c44-5", "G6-C4-4", "micro_writing", "hard",
           "【高分微写作】请以「暖」或「难忘的一幕」为中心，写一段 85～130 字的小升初高分微片段。要求：包含环境烘托或人物细节特写（动作/神态），至少运用一种修辞手法（比喻、拟人或排比），真情自然流露。",
           "紧扣“暖”或“难忘的一幕”立意，兼具环境烘托、人物动作神态特写与修辞手法，情感真挚饱满。",
           "写作锦囊：采用“环境镜头 + 人物慢动作特写 + 内心感悟升华”三层结构。",
           rubric_keywords=[["暖", "心", "感动", "难忘", "眼眶", "温"], ["手", "眼", "笑", "肩", "灯", "风", "雨", "光", "茶", "伞"], ["像", "仿佛", "犹如", "化作", "流淌", "照亮"]],
           min_chars=85,
           sample_answer="冬夜的寒风在窗外呼啸，台灯下我正为一道难题愁眉不展。门轻轻推开，妈妈端着一杯热牛奶走进来，带着薄茧的掌心温柔地抚平我紧锁的眉头。乳白的灯光洒在她鬓角的几丝白发上，那杯中升腾的热气化作一股暖流，瞬间融化了冬夜的寒意，也照亮了我心底最柔软的角落。",
           scaffolds=[
               "三层高分结构：环境铺垫（冬夜寒风/雨幕/教室夕阳）→ 人物慢镜头特写（眼神/掌心/动作）→ 情感点题升华",
               "好词锦囊：春风化雨、热泪盈眶、沁人心脾、如沐春风、镌刻心底",
               "修辞支架：那温暖的目光像一束柔和的春光，瞬间照亮了……",
           ]),
        _q("g6-c44-6", "G6-C4-4", "micro_writing", "hard",
           "【高分微写作】即将告别小学六年时光，请运用「点面结合」或「排比抒情」，写一段 85～130 字的校园毕业微片段（如一次运动会冲线、最后一堂语文课或校园一角）。",
           "运用点面结合或排比修辞，展现校园生活场景与对母校、师生同窗的深厚眷恋。",
           "写作锦囊：可先用排比回眸六年剪影（面），再定格老师或挚友的一个特写镜头（点）。",
           rubric_keywords=[["校园", "教室", "操场", "黑板", "六年", "毕业", "母校", "同窗", "老师"], ["笑", "声", "眼", "手", "光", "风", "树", "书"], ["像", "仿佛", "难忘", "珍藏", "青春", "成长"]],
           min_chars=85,
           sample_answer="六年的时光像一首流淌在梧桐树下的歌：这里有早读课上琅琅的书声，有绿茵场上并肩奔跑的汗水，也有运动会看台上震耳欲聋的呐喊。最难忘最后一堂课上，老师握着粉笔在黑板上郑重写下“前程似锦”，转身时眼角闪烁的泪光与温柔的微笑，永远定格成我少年时代最珍贵的画卷。",
           scaffolds=[
               "排比开头（面）：六年的时光像一首动人的歌：这里有……，有……，也有……",
               "特写定格（点）：最难忘那一刻，老师/同桌……（写出动作、眼神或一句话）",
               "好词锦囊：书声琅琅、并肩同行、前程似锦、岁月如歌、镌刻心间",
           ]),
    ]

    return bank


CHINESE_G3_QUESTIONS = _build_g3_questions()
CHINESE_G4_QUESTIONS = _build_g4_questions()
CHINESE_G6_QUESTIONS = _build_g6_questions()

QUESTIONS_BY_GRADE: dict[int, dict[str, list[dict[str, Any]]]] = {
    3: CHINESE_G3_QUESTIONS,
    4: CHINESE_G4_QUESTIONS,
    6: CHINESE_G6_QUESTIONS,
}


# ---------------- G3 / G4 / G6 应试专项（每年级 4 个：基/诗/读/写） ----------------
CHINESE_G3_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g3-chinese-foundation-sprint",
        "subject": "语文",
        "grade": 3,
        "section": "foundation",
        "sectionLabel": "基",
        "title": "三年级基础 · 字词句启蒙速通专项",
        "subtitle": "声韵母多音字、偏旁形近字、ABB/四字词语、把被句与提示语标点，配字块托盘辅助，单题宽松限时 25 秒",
        "icon": "⚡",
        "timingMode": "per_question",
        "perQuestionSec": 25,
        "maxPlays": 3,
        "timeLimitSec": 450,
        "questionCount": 10,
        "nodeKeys": ["G3-C1-1", "G3-C1-2", "G3-C1-3", "G3-C1-4", "G3-C2-1", "G3-C2-2", "G3-C2-3", "G3-C2-4"],
        "typeMix": {"dictation_spell": 3, "basic_choice": 4, "error_spot": 2, "sentence_choice": 1},
    },
    {
        "slug": "g3-chinese-poetry-sprint",
        "subject": "语文",
        "grade": 3,
        "section": "poetry",
        "sectionLabel": "诗",
        "title": "三年级古诗文 · 写景节日古诗与小古文专项",
        "subtitle": "《山行》《望天门山》《元日》《司马光》《守株待兔》与谚语格言，配候选字块辅助默写，10 分钟整体倒计时",
        "icon": "📜",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 3,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": ["G3-C3-1", "G3-C3-2", "G3-C3-3", "G3-C3-4"],
        "typeMix": {"poem_fill": 4, "reading_choice": 6},
    },
    {
        "slug": "g3-chinese-reading-sprint",
        "subject": "语文",
        "grade": 3,
        "section": "reading",
        "sectionLabel": "读",
        "title": "三年级阅读 · 中心句与童话观察阅读专项",
        "subtitle": "找段落中心句、童话寓言道理体会与自然动植物观察短文，含句式支架简答，15 分钟整体倒计时",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["G3-C4-1", "G3-C4-2", "G3-C4-3"],
        "typeMix": {"reading_choice": 6, "reading_short": 2},
    },
    {
        "slug": "g3-chinese-writing-sprint",
        "subject": "语文",
        "grade": 3,
        "section": "writing",
        "sectionLabel": "写",
        "title": "三年级表达 · 观察写话与50字微段落专项",
        "subtitle": "比喻拟人造句、标点病句诊治 + 配开头句式支架与好词锦囊的 50 字微写话，15 分钟整体倒计时",
        "icon": "🖋️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["G3-C2-2", "G3-C2-4", "G3-C4-3", "G3-C4-4"],
        "typeMix": {"error_spot": 2, "sentence_choice": 2, "reading_choice": 2, "micro_writing": 2},
    },
]

CHINESE_G4_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g4-chinese-foundation-sprint",
        "subject": "语文",
        "grade": 4,
        "section": "foundation",
        "sectionLabel": "基",
        "title": "四年级基础 · 字词成语与句式速通专项",
        "subtitle": "语境多音字、形声字辨析、神话历史成语、关联词与反问设问病句，单题限时 22 秒进阶训练",
        "icon": "⚡",
        "timingMode": "per_question",
        "perQuestionSec": 22,
        "maxPlays": 2,
        "timeLimitSec": 400,
        "questionCount": 10,
        "nodeKeys": ["G4-C1-1", "G4-C1-2", "G4-C1-3", "G4-C1-4", "G4-C2-1", "G4-C2-2", "G4-C2-3", "G4-C2-4"],
        "typeMix": {"dictation_spell": 3, "basic_choice": 4, "error_spot": 2, "sentence_choice": 1},
    },
    {
        "slug": "g4-chinese-poetry-sprint",
        "subject": "语文",
        "grade": 4,
        "section": "poetry",
        "sectionLabel": "诗",
        "title": "四年级古诗文 · 哲理边塞古诗与神话小古文专项",
        "subtitle": "《题西林壁》《暮江吟》《出塞》《精卫填海》《王戎不取道旁李》与八字成语，10 分钟整体倒计时",
        "icon": "📜",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 2,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": ["G4-C3-1", "G4-C3-2", "G4-C3-3", "G4-C3-4"],
        "typeMix": {"poem_fill": 4, "reading_choice": 6},
    },
    {
        "slug": "g4-chinese-reading-sprint",
        "subject": "语文",
        "grade": 4,
        "section": "reading",
        "sectionLabel": "读",
        "title": "四年级阅读 · 批注提问与事件概括专项",
        "subtitle": "起因经过结果概括、多角度提问批注与人物连续动作心理分析，AI 实时批改简答，15 分钟整体倒计时",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["G4-C4-1", "G4-C4-2", "G4-C4-3"],
        "typeMix": {"reading_choice": 6, "reading_short": 2},
    },
    {
        "slug": "g4-chinese-writing-sprint",
        "subject": "语文",
        "grade": 4,
        "section": "writing",
        "sectionLabel": "写",
        "title": "四年级表达 · 动作细节升格与80字微写作专项",
        "subtitle": "连续动作刻画、病句修改 + 配好词锦囊的 80 字微片段写作，AI 实时点评，15 分钟整体倒计时",
        "icon": "🖋️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["G4-C2-3", "G4-C2-4", "G4-C4-3", "G4-C4-4"],
        "typeMix": {"error_spot": 2, "sentence_choice": 2, "reading_choice": 2, "micro_writing": 2},
    },
]

CHINESE_G6_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g6-chinese-foundation-sprint",
        "subject": "语文",
        "grade": 6,
        "section": "foundation",
        "sectionLabel": "基",
        "title": "六年级基础 · 小升初字词句综合速通专项",
        "subtitle": "高频多音字、形近同音字、成语感情色彩、复杂复句、两面对一面病句与转述双重否定，单题限时 20 秒",
        "icon": "⚡",
        "timingMode": "per_question",
        "perQuestionSec": 20,
        "maxPlays": 2,
        "timeLimitSec": 360,
        "questionCount": 10,
        "nodeKeys": ["G6-C1-1", "G6-C1-2", "G6-C1-3", "G6-C1-4", "G6-C2-1", "G6-C2-2", "G6-C2-3", "G6-C2-4"],
        "typeMix": {"dictation_spell": 3, "basic_choice": 4, "error_spot": 2, "sentence_choice": 1},
    },
    {
        "slug": "g6-chinese-poetry-sprint",
        "subject": "语文",
        "grade": 6,
        "section": "poetry",
        "sectionLabel": "诗",
        "title": "六年级古诗文 · 托物言志诗词与经典文言专项",
        "subtitle": "《石灰吟》《竹石》《西江月》《七律·长征》《伯牙鼓琴》《学弈》《两小儿辩日》与国学常识，10 分钟倒计时",
        "icon": "📜",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 2,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": ["G6-C3-1", "G6-C3-2", "G6-C3-3", "G6-C3-4"],
        "typeMix": {"poem_fill": 4, "reading_choice": 6},
    },
    {
        "slug": "g6-chinese-reading-sprint",
        "subject": "语文",
        "grade": 6,
        "section": "reading",
        "sectionLabel": "读",
        "title": "六年级阅读 · 小说环境点面与非连续文本专项",
        "subtitle": "点面结合与环境描写作用、小说人物主旨提炼与多材料非连续性文本整合，AI 批改简答，15 分钟倒计时",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["G6-C4-1", "G6-C4-2", "G6-C4-3"],
        "typeMix": {"reading_choice": 6, "reading_short": 2},
    },
    {
        "slug": "g6-chinese-writing-sprint",
        "subject": "语文",
        "grade": 6,
        "section": "writing",
        "sectionLabel": "写",
        "title": "六年级表达 · 小升初审题立意与100字高分微写作专项",
        "subtitle": "复杂病句诊治、修辞标点精析 + AI 实时批改 100 字融情于景/点面结合高分微写作，15 分钟倒计时",
        "icon": "🖋️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["G6-C2-2", "G6-C2-4", "G6-C4-1", "G6-C4-4"],
        "typeMix": {"error_spot": 2, "sentence_choice": 2, "reading_choice": 2, "micro_writing": 2},
    },
]

SPRINTS_BY_GRADE: dict[int, list[dict[str, Any]]] = {
    3: CHINESE_G3_SPRINTS,
    4: CHINESE_G4_SPRINTS,
    6: CHINESE_G6_SPRINTS,
}

__all__ = [
    "CHINESE_DOMAINS",
    "CHINESE_G3_NODES",
    "CHINESE_G3_QUESTIONS",
    "CHINESE_G3_SPRINTS",
    "CHINESE_G4_NODES",
    "CHINESE_G4_QUESTIONS",
    "CHINESE_G4_SPRINTS",
    "CHINESE_G6_NODES",
    "CHINESE_G6_QUESTIONS",
    "CHINESE_G6_SPRINTS",
    "NODES_BY_GRADE",
    "QUESTIONS_BY_GRADE",
    "SPRINTS_BY_GRADE",
    "build_assist_tiles",
]
