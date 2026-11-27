"""语文通用知识地图（去教材版本强绑定）与多题型自带题引擎.

设计原则：
- 按小学五年级通用课标核心知识域组织 4 大岛屿、16 个节点（字词与语音 / 句子与修辞 / 古诗文与积累 / 阅读方法与表达），不强绑定教材版本。
- 支持 10 类语文核心题型：
  - 地图轻辅助：basic_choice（字音/字形/成语单选）、hanzi_tiles（字块拼词）、poem_tiles（古诗字块点选默写）、error_spot（病句点击找茬）、sentence_choice（关联词/句式/修辞单选）、reading_choice（阅读/古诗文单选）。
  - 专项强应试：dictation_spell（听写/看拼音键盘写词）、poem_fill（古诗纯键盘精准默写）、reading_short（现代文阅读简答，AI 实时批改+规则兜底）、micro_writing（100 字微片段写作，AI 实时批改+规则兜底）。
- 听写词条与古诗文朗诵均声明确定性 audioId 与 audioText，由 scripts/build_chinese_arena_audio.py 离线预生成静态普通话 MP3。
"""
from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Iterable

SUBJECT_CHINESE = "语文"
DEFAULT_GRADE = 5

LIGHT_STATES = {
    "unexplored": "未探索",
    "exploring": "探索中",
    "lit": "已点亮",
    "mastered": "精通",
}

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

MAP_FRIENDLY_TYPES = {
    "basic_choice",
    "hanzi_tiles",
    "poem_tiles",
    "error_spot",
    "sentence_choice",
    "reading_choice",
}

SUBJECTIVE_TYPES = {"reading_short", "micro_writing"}

CHINESE_G5_DOMAINS: list[dict[str, Any]] = [
    {"id": "words", "name": "字词与语音", "icon": "🔤", "color": "#a8101c"},
    {"id": "sentence", "name": "句子与修辞", "icon": "✍️", "color": "#0b8f5a"},
    {"id": "poetry", "name": "古诗文与积累", "icon": "📜", "color": "#b45309"},
    {"id": "reading", "name": "阅读方法与表达", "icon": "📖", "color": "#1e4e79"},
]

CHINESE_G5_NODES: list[dict[str, Any]] = [
    # C1 字词与语音
    {"key": "C1-1", "name": "多音字与易错读音", "domain": "words", "icon": "🗣️"},
    {"key": "C1-2", "name": "形近字与同音字辨析", "domain": "words", "icon": "🔎"},
    {"key": "C1-3", "name": "高频成语与近反义词", "domain": "words", "icon": "🏮"},
    {"key": "C1-4", "name": "听写与看拼音写词语", "domain": "words", "icon": "🎧"},
    # C2 句子与修辞
    {"key": "C2-1", "name": "常用关联词与复句", "domain": "sentence", "icon": "🔗"},
    {"key": "C2-2", "name": "常见病句诊断与修改", "domain": "sentence", "icon": "🩺"},
    {"key": "C2-3", "name": "句式转换（把/被/反问/转述）", "domain": "sentence", "icon": "🔄"},
    {"key": "C2-4", "name": "修辞手法与标点符号", "domain": "sentence", "icon": "✨"},
    # C3 古诗文与积累
    {"key": "C3-1", "name": "写景抒情必背古诗", "domain": "poetry", "icon": "🏞️"},
    {"key": "C3-2", "name": "爱国送别与哲理古诗", "domain": "poetry", "icon": "🚩"},
    {"key": "C3-3", "name": "小古文重点实词与句意", "domain": "poetry", "icon": "📖"},
    {"key": "C3-4", "name": "名言警句与俗语积累", "domain": "poetry", "icon": "💬"},
    # C4 阅读方法与表达
    {"key": "C4-1", "name": "抓关键句与概括主要内容", "domain": "reading", "icon": "🎯"},
    {"key": "C4-2", "name": "说明方法与说明文细节", "domain": "reading", "icon": "🔬"},
    {"key": "C4-3", "name": "人物描写与情感体会", "domain": "reading", "icon": "❤️"},
    {"key": "C4-4", "name": "审题立意与细节升格", "domain": "reading", "icon": "🖋️"},
]

NODE_BY_KEY = {n["key"]: n for n in CHINESE_G5_NODES}
DOMAIN_BY_ID = {d["id"]: d for d in CHINESE_G5_DOMAINS}


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


def _q(
    qid: str,
    node_key: str,
    qtype: str,
    level: str,
    text: str,
    answer: str,
    explanation: str,
    *,
    options: list[str] | None = None,
    correct_index: int | None = None,
    audio_text: str | None = None,
    audio_voice: str = "zh-CN-XiaoxiaoNeural",
    hint: str = "",
    tiles: list[str] | None = None,
    passage: str | None = None,
    rubric_keywords: list[list[str]] | None = None,
    min_chars: int = 0,
    sample_answer: str = "",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": qid,
        "nodeKey": node_key,
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
    if passage:
        item["passage"] = passage
    if rubric_keywords:
        item["rubricKeywords"] = [list(g) for g in rubric_keywords]
    if min_chars:
        item["minChars"] = int(min_chars)
    if sample_answer:
        item["sampleAnswer"] = sample_answer
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
        f"听读音并根据拼音「{pinyin}」，点击字块拼出正确词语：",
        word,
        explanation,
        tiles=tiles,
        hint=f"共 {len(word)} 个字",
        audio_text=audio_text or word,
    )


def _poem_tile_q(
    qid: str,
    node_key: str,
    level: str,
    prompt: str,
    line: str,
    distractors: list[str],
    explanation: str,
    audio_text: str,
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


def _build_question_bank() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in CHINESE_G5_NODES}

    # ---------------- C1-1 多音字与易错读音 ----------------
    bank["C1-1"] = [
        _q("c11-1", "C1-1", "basic_choice", "basic",
           "“勉强”中“强”的正确读音是哪一项？", "qiǎng",
           "表示“硬要、迫使、尽力而为”时读 qiǎng，如勉强、强迫。",
           options=["qiáng", "qiǎng", "jiàng", "qiāng"], correct_index=1),
        _q("c11-2", "C1-1", "basic_choice", "basic",
           "“间隔”中“间”的正确读音是哪一项？", "jiàn",
           "表示“隔开、不连接”时读 jiàn，如间隔、间断、黑白相间。",
           options=["jiān", "jiàn", "jiǎn", "jìn"], correct_index=1),
        _q("c11-3", "C1-1", "basic_choice", "medium",
           "下列加点字读音完全正确的一组是：", "冠军(guàn)  削弱(xuē)",
           "“冠军”读 guàn（第一名）；“削弱”书面语读 xuē；“便宜”表价低读 pián。",
           options=["冠军(guān)  削弱(xiāo)", "冠军(guàn)  削弱(xuē)", "便宜(biàn)  待会儿(dài)", "龟裂(guī)  计划(huá)"],
           correct_index=1),
        _q("c11-4", "C1-1", "basic_choice", "medium",
           "“待会儿我们就出发”中“待”的读音是：", "dāi",
           "表示“停留、过一会儿”时口语读 dāi；表示“等待、对待”时读 dài。",
           options=["dài", "dāi", "dǎi", "tài"], correct_index=1),
        _q("c11-5", "C1-1", "basic_choice", "hard",
           "下列句子中“落”字读音与其他三项不同的是：", "他总是丢三落四，把作业忘在家里。",
           "“丢三落四”中“落”表示遗漏，读 là；其余“降落、落叶、落地”均读 luò。",
           options=["秋风吹过，树叶纷纷飘落。", "飞机平稳地降落在跑道上。", "他总是丢三落四，把作业忘在家里。", "太阳落山后，天色渐渐暗了下来。"],
           correct_index=2),
        _q("c11-6", "C1-1", "dictation_spell", "medium",
           "听录音，直接用键盘写出你听到的易错词语（提示：miǎn qiǎng）：", "勉强",
           "“勉强”注意不要写成“免强”，读作 miǎn qiǎng。",
           hint="2 个汉字", audio_text="勉强"),
    ]

    # ---------------- C1-2 形近字与同音字辨析 ----------------
    bank["C1-2"] = [
        _q("c12-1", "C1-2", "basic_choice", "basic",
           "下列词语中书写完全没有错别字的一项是：", "协调有序",
           "“协调有序”书写正确；其余应为“金碧辉煌”“不可估量”“应接不暇”。",
           options=["金壁辉煌", "不可古量", "协调有序", "应接不瑕"], correct_index=2),
        _hanzi_tile_q("c12-2", "C1-2", "basic", "懒惰", "lǎn duò", ["赖", "坠"],
                      "“懒惰”两字均为竖心旁，与心性懒散有关。", seed=12),
        _q("c12-3", "C1-2", "basic_choice", "medium",
           "“我按____不住内心的激动”横线上应填哪个字？", "捺",
           "“按捺不住”意为压抑不住，用提手旁的“捺”，不写作“耐”或“奈”。",
           options=["耐", "奈", "捺", "纳"], correct_index=2),
        _hanzi_tile_q("c12-4", "C1-2", "medium", "侵略", "qīn lüè", ["浸", "路"],
                      "“侵略”的“侵”是单人旁，不是三点水“浸”。", seed=13),
        _q("c12-5", "C1-2", "basic_choice", "hard",
           "选出下面词语中没有错别字的一组：", "酬谢  叮嘱  崩塌",
           "“酬谢、叮嘱、崩塌”完全正确；其余错在“豪不犹豫(毫)”“同心协力(协)”“再接再励(厉)”。",
           options=["豪不犹豫  一泻千里", "同心胁力  理所当然", "酬谢  叮嘱  崩塌", "再接再励  负荆请罪"],
           correct_index=2),
        _q("c12-6", "C1-2", "dictation_spell", "hard",
           "听录音，根据语境直接用键盘写出正确词语（提示：fēn fù，嘱咐安排）：", "吩咐",
           "“吩咐”两字都是口字旁，表示口头指派或嘱咐。",
           hint="2 个汉字，注意偏旁", audio_text="吩咐"),
    ]

    # ---------------- C1-3 高频成语与近反义词 ----------------
    bank["C1-3"] = [
        _q("c13-1", "C1-3", "basic_choice", "basic",
           "下列成语与“鼻子都气歪了”意思最相近的是：", "气急败坏",
           "“气急败坏”形容十分慌张或恼怒，与俗语“鼻子都气歪了”意思对应。",
           options=["气急败坏", "得意忘形", "足智多谋", "兴高采烈"], correct_index=0),
        _q("c13-2", "C1-3", "basic_choice", "basic",
           "“足智多谋”和“诡计多端”的区别在于：", "前者是褒义词，后者是贬义词",
           "两者都指主意多，但“足智多谋”赞美智慧（褒义），“诡计多端”批评狡诈（贬义）。",
           options=["前者是贬义词，后者是褒义词", "前者是褒义词，后者是贬义词", "两者感情色彩完全相同", "两者都只能形容古代人物"],
           correct_index=1),
        _hanzi_tile_q("c13-3", "C1-3", "medium", "安居乐业", "ān jū lè yè", ["举", "夜"],
                      "“安居乐业”形容安定地生活，愉快地工作。", seed=14),
        _q("c13-4", "C1-3", "basic_choice", "medium",
           "下列句子中加点成语使用恰当的一项是：", "同学们同心协力，很快就打扫完了教室。",
           "“同心协力”指团结一致共同努力，符合打扫教室的积极语境。",
           options=["他每天臭名远扬地帮助同学。", "同学们同心协力，很快就打扫完了教室。", "小亮处心积虑地完成了今天的家庭作业。", "大家喋喋不休地举手回答了老师的问题。"],
           correct_index=1),
        _q("c13-5", "C1-3", "basic_choice", "hard",
           "与“吃水不忘挖井人”意思最接近的成语是：", "饮水思源",
           "“饮水思源”比喻不忘本，与“吃水不忘挖井人”完全对应。",
           options=["望梅止渴", "饮水思源", "画龙点睛", "自相矛盾"], correct_index=1),
        _q("c13-6", "C1-3", "dictation_spell", "hard",
           "听录音，用键盘写出这个表示“形容非常着急或惊慌”的四字成语：", "迫不及待",
           "“迫不及待”注意是“及”而不是“急”。",
           hint="4 个汉字", audio_text="迫不及待"),
    ]

    # ---------------- C1-4 听写与看拼音写词语 ----------------
    bank["C1-4"] = [
        _hanzi_tile_q("c14-1", "C1-4", "basic", "恩惠", "ēn huì", ["思", "慧"],
                      "“恩惠”表示给予的或受到的好处，“惠”下为心。", seed=15),
        _hanzi_tile_q("c14-2", "C1-4", "basic", "平衡", "píng héng", ["评", "恒"],
                      "“平衡”意为平稳、对等，不要写作“评恒”。", seed=16),
        _hanzi_tile_q("c14-3", "C1-4", "medium", "辉煌", "huī huáng", ["灰", "皇"],
                      "“辉煌”形容光辉灿烂，两字分别含光、火。", seed=17),
        _q("c14-4", "C1-4", "dictation_spell", "medium",
           "听录音并结合拼音「fán zhí」，用键盘写出正确词语：", "繁殖",
           "“繁殖”指生物产生新的个体，“殖”为歹字旁。",
           hint="2 个汉字", audio_text="繁殖"),
        _q("c14-5", "C1-4", "dictation_spell", "hard",
           "听录音并结合拼音「lí míng」，用键盘写出表示天快亮时的词语：", "黎明",
           "“黎明”指天快要亮或刚亮的时候，注意“黎”的写法。",
           hint="2 个汉字", audio_text="黎明"),
        _q("c14-6", "C1-4", "dictation_spell", "hard",
           "听录音并结合拼音「lǐng lüè」，用键盘写出正确词语：", "领略",
           "“领略”意为了解事物的情况，进而认识它的意义或辨别它的滋味。",
           hint="2 个汉字", audio_text="领略"),
    ]

    # ---------------- C2-1 常用关联词与复句 ----------------
    bank["C2-1"] = [
        _q("c21-1", "C2-1", "sentence_choice", "basic",
           "“____明天天气晴朗，我们____去植物园观察落叶。”最恰当的关联词是：", "如果……就……",
           "前半句提出假设条件，后半句说明结果，用假设关系关联词“如果……就……”。",
           options=["因为……所以……", "如果……就……", "虽然……但是……", "不但……而且……"], correct_index=1),
        _q("c21-2", "C2-1", "sentence_choice", "basic",
           "“松鼠____有时也捕捉鸟雀，____不是肉食动物。”横线上应填：", "虽然……却……",
           "前后两句意思形成转折，应选转折关系关联词“虽然……却……”。",
           options=["只要……就……", "虽然……却……", "既然……就……", "无论……都……"], correct_index=1),
        _q("c21-3", "C2-1", "sentence_choice", "medium",
           "“____遇到多大的困难，我们____不能放弃。”最恰当的关联词是：", "无论……都……",
           "表示在任何条件下结果不变，用条件关系关联词“无论……都……”。",
           options=["只有……才……", "无论……都……", "既……又……", "不是……而是……"], correct_index=1),
        _q("c21-4", "C2-1", "sentence_choice", "medium",
           "“花生____不好看，____很有用。”下列关联词填入最贴切的是：", "虽然……可是……",
           "外表不好看与内在很有用构成明显转折。",
           options=["因为……所以……", "虽然……可是……", "即使……也……", "与其……不如……"], correct_index=1),
        _q("c21-5", "C2-1", "sentence_choice", "hard",
           "下面句子中关联词使用有误的一项是：", "只要下大雨，运动会也照常举行。",
           "“下大雨”与“照常举行”是让步假设关系，应改为“即使……也……”，不能用“只要……也……”。",
           options=["因为坚持每天阅读，所以她的写作进步很快。", "只要下大雨，运动会也照常举行。", "只有认真审题，才能避免答非所问。", "这本书不但故事精彩，而且插图精美。"],
           correct_index=1),
        _q("c21-6", "C2-1", "sentence_choice", "hard",
           "“____空谈理想，____踏踏实实迈出第一步。”最恰当的选择关系关联词是：", "与其……不如……",
           "在两者中取后者舍前者，应使用“与其……不如……”。",
           options=["与其……不如……", "宁可……也不……", "或者……或者……", "不但……而且……"], correct_index=0),
    ]

    # ---------------- C2-2 常见病句诊断与修改 ----------------
    bank["C2-2"] = [
        _q("c22-1", "C2-2", "error_spot", "basic",
           "找出下面病句的病因：「通过这次科普讲座，使我学到了很多天文知识。」", "缺少主语",
           "“通过……”和“使……”同时使用导致句子没有主语，删去“通过”或“使”即可。",
           options=["缺少主语", "语序颠倒", "用词重复", "前后矛盾"], correct_index=0),
        _q("c22-2", "C2-2", "error_spot", "basic",
           "找出下面病句的病因：「我断定他大概已经完成了今天的背诵任务。」", "前后矛盾",
           "“断定”（十分肯定）与“大概”（不确定）意思互相矛盾，应删去其一。",
           options=["搭配不当", "前后矛盾", "分类不当", "指代不明"], correct_index=1),
        _q("c22-3", "C2-2", "error_spot", "medium",
           "找出下面病句的病因：「果园里种着苹果、梨、西瓜和许多水果。」", "分类不当（概念包含）",
           "苹果、梨、西瓜本身就属于水果，不能与“许多水果”并列，应删去“和许多水果”或改为“等水果”。",
           options=["成分残缺", "语序不当", "分类不当（概念包含）", "否定不当"], correct_index=2),
        _q("c22-4", "C2-2", "error_spot", "medium",
           "找出下面病句的病因：「为了防止不再发生安全事故，学校加强了巡查。」", "否定不当",
           "“防止”和“不再”双重否定反而变成了“希望发生事故”，应删去“不”。",
           options=["搭配不当", "否定不当", "用词重复", "缺少宾语"], correct_index=1),
        _q("c22-5", "C2-2", "sentence_choice", "hard",
           "下列句子中没有语病的一项是：", "我们要养成勤于思考、认真观察的好习惯。",
           "A 缺主语；B 重复（大约/左右）；D 搭配不当（提高……数量应改为增加数量）。",
           options=["听了英雄的事迹，让我深受感动。", "校园里大约有二十棵左右的桂花树。", "我们要养成勤于思考、认真观察的好习惯。", "今年图书馆提高了课外书的数量。"],
           correct_index=2),
        _q("c22-6", "C2-2", "error_spot", "hard",
           "找出下面病句的病因：「他忍不住情不自禁地笑出声来。」", "语义重复",
           "“忍不住”和“情不自禁”意思重复，保留其中一个即可。",
           options=["语义重复", "缺少主语", "前后矛盾", "语序颠倒"], correct_index=0),
    ]

    # ---------------- C2-3 句式转换（把/被/反问/转述） ----------------
    bank["C2-3"] = [
        _q("c23-1", "C2-3", "sentence_choice", "basic",
           "把反问句“这难道不是一幅美丽的画卷吗？”改为陈述句，正确的一项是：", "这是一幅美丽的画卷。",
           "反问句改陈述句：去掉“难道”“不”“吗”，问号改句号，保持原意不变。",
           options=["这不是一幅美丽的画卷。", "这是一幅美丽的画卷。", "这是一幅美丽的画卷吗？", "这怎么会是一幅美丽的画卷。"],
           correct_index=1),
        _q("c23-2", "C2-3", "sentence_choice", "basic",
           "把直述句“妈妈对我说：‘我明天带你去博物馆。’”改为转述句，正确的是：", "妈妈对我说，她明天带我去博物馆。",
           "直述改转述：冒号引号改逗号，“我”改为“她”，“你”改为“我”。",
           options=["妈妈对我说，我明天带你去博物馆。", "妈妈对我说，她明天带我去博物馆。", "妈妈对我说，她明天带你去博物馆。", "妈妈对我说，我明天带她去博物馆。"],
           correct_index=1),
        _q("c23-3", "C2-3", "sentence_choice", "medium",
           "把“一阵大风吹散了天空中的乌云”改为“被”字句，正确的一项是：", "天空中的乌云被一阵大风吹散了。",
           "“被”字句结构：受事者（天空中的乌云）+ 被 + 施事者（一阵大风）+ 动作（吹散了）。",
           options=["一阵大风被天空中的乌云吹散了。", "天空中的乌云被一阵大风吹散了。", "天空中的乌云把一阵大风吹散了。", "一阵大风把天空中的乌云吹散了。"],
           correct_index=1),
        _q("c23-4", "C2-3", "sentence_choice", "medium",
           "把“我们不能忘记先辈的付出”改为双重否定句，最准确的是：", "我们不得不铭记先辈的付出。",
           "双重否定表达强烈肯定语气，且不可改变原句“要铭记”的含义。",
           options=["我们怎么能忘记先辈的付出？", "我们不得不铭记先辈的付出。", "我们不应该不忘记先辈的付出。", "我们没有理由记住先辈的付出。"],
           correct_index=1),
        _q("c23-5", "C2-3", "sentence_choice", "hard",
           "下列缩句最准确的一项是：「洁白的雪花纷纷扬扬地落在光秃秃的枝头。」", "雪花落在枝头。",
           "缩句保留主谓宾主干（雪花/落在/枝头），删去所有定语和状语修饰成分。",
           options=["雪花落在枝头。", "洁白的雪花落在枝头。", "雪花纷纷扬扬地落。", "雪花在光秃秃的枝头。"],
           correct_index=0),
        _q("c23-6", "C2-3", "sentence_choice", "hard",
           "直述改转述：“小华对老师说：‘这道题我已经订正好了。’”正确改写是：", "小华对老师说，那道题他已经订正好了。",
           "指示代词“这”在转述时通常改为“那”，人称“我”改为“他”。",
           options=["小华对老师说，这道题我已经订正好了。", "小华对老师说，那道题他已经订正好了。", "小华对老师说，那道题我已经订正好了。", "小华对老师说：“那道题他已经订正好了。”"],
           correct_index=1),
    ]

    # ---------------- C2-4 修辞手法与标点符号 ----------------
    bank["C2-4"] = [
        _q("c24-1", "C2-4", "sentence_choice", "basic",
           "“白鹭是一首精巧的诗。”这句话运用的修辞手法是：", "比喻",
           "把“白鹭”比作“精巧的诗”，属于暗喻（比喻）。",
           options=["比喻", "拟人", "夸张", "排比"], correct_index=0),
        _q("c24-2", "C2-4", "sentence_choice", "basic",
           "“微风吹过，柳枝欢快地跳起了舞。”这句话运用的修辞手法是：", "拟人",
           "赋予柳枝人“欢快跳舞”的动作与情感，属于拟人。",
           options=["比喻", "拟人", "设问", "反问"], correct_index=1),
        _q("c24-3", "C2-4", "sentence_choice", "medium",
           "下列句子中顿号使用正确的一项是：", "书架上摆着童话、寓言、科普读物和历史故事。",
           "并列词语之间用顿号，最后两项之间已有“和”字不再加顿号；约数（七八岁）之间不加顿号。",
           options=["他大概有七、八岁。", "书架上摆着童话、寓言、科普读物和历史故事。", "我们要学习语文、数学、和英语。", "公园里开满了红的、白的、黄的花、真好看。"],
           correct_index=1),
        _q("c24-4", "C2-4", "sentence_choice", "medium",
           "“读书有什么好处？读书可以开阔眼界，增长智慧。”运用的修辞手法是：", "设问",
           "自问自答以引起读者注意和思考，属于设问。",
           options=["反问", "设问", "排比", "对比"], correct_index=1),
        _q("c24-5", "C2-4", "sentence_choice", "hard",
           "下面句子中引号的作用是：「他真是个“小书虫”，一进图书馆就舍不得出来。」", "表示特定称谓",
           "“小书虫”是对爱读书孩子的亲切外号，属于特定称谓。",
           options=["表示直接引用", "表示讽刺否定", "表示特定称谓", "表示着重强调"], correct_index=2),
        _q("c24-6", "C2-4", "sentence_choice", "hard",
           "下列句子中冒号使用最恰当的一项是：", "它要是高兴，能比谁都温柔可亲：用身子蹭你的腿，把脖子伸出来让你给它抓痒。",
           "冒号用于引出后面具体的解释说明；提示语在中间时不用冒号，而用逗号。",
           options=["“快看，”小明指着天空说：“一道彩虹！”", "它要是高兴，能比谁都温柔可亲：用身子蹭你的腿，把脖子伸出来让你给它抓痒。", "我喜欢吃的水果有：苹果、香蕉和草莓。", "老师问：“你昨天去哪儿了”："],
           correct_index=1),
    ]

    # ---------------- C3-1 写景抒情必背古诗 ----------------
    bank["C3-1"] = [
        _poem_tile_q("c31-1", "C3-1", "basic",
                     "听朗诵并点选字块，补全王维《山居秋暝》名句：「明月松间照，____。」",
                     "清泉石上流", ["青", "水"],
                     "“明月松间照，清泉石上流”一静一动，描绘了雨后秋山的清幽之美。",
                     audio_text="明月松间照，清泉石上流。", seed=31),
        _poem_tile_q("c31-2", "C3-1", "basic",
                     "听朗诵并点选字块，补全张继《枫桥夜泊》名句：「月落乌啼霜满天，____。」",
                     "江枫渔火对愁眠", ["鱼", "船"],
                     "注意是“渔火”（渔船上的灯火），不是“鱼火”。",
                     audio_text="月落乌啼霜满天，江枫渔火对愁眠。", seed=32),
        _q("c31-3", "C3-1", "reading_choice", "medium",
           "“竹喧归浣女，莲动下渔舟”中“浣女”指的是：", "洗衣服的女子",
           "“浣”意为洗涤，“浣女”即在溪边洗衣服的女子。",
           options=["采莲的渔夫", "洗衣服的女子", "砍柴的农夫", "弹琴的少女"],
           correct_index=1, audio_text="竹喧归浣女，莲动下渔舟。", audio_voice="zh-CN-YunxiNeural"),
        _q("c31-4", "C3-1", "poem_fill", "medium",
           "听朗诵，直接用键盘精准默写下句：「西塞山前白鹭飞，________。」（不加标点）",
           "桃花流水鳜鱼肥",
           "张志和《渔歌子》名句，注意“鳜”字写法，不要写错别字。",
           hint="7 个汉字，出自《渔歌子》", audio_text="西塞山前白鹭飞，桃花流水鳜鱼肥。", audio_voice="zh-CN-YunxiNeural"),
        _q("c31-5", "C3-1", "poem_fill", "hard",
           "听朗诵，精准默写《枫桥夜泊》后两句中的末句：「姑苏城外寒山寺，________。」",
           "夜半钟声到客船",
           "“夜半钟声到客船”以声衬静，抒发了游子孤寂的羁旅之愁。",
           hint="7 个汉字", audio_text="姑苏城外寒山寺，夜半钟声到客船。", audio_voice="zh-CN-YunxiNeural"),
        _q("c31-6", "C3-1", "reading_choice", "hard",
           "纳兰性德《长相思》中“风一更，雪一更，聒碎乡心梦不成”的“聒”意为：", "声音嘈杂，这里指风雪声",
           "“聒”表示声音嘈杂，风雪交加的声音打碎了思乡之梦。",
           options=["轻柔吹拂", "声音嘈杂，这里指风雪声", "大雪覆盖", "快速奔跑"],
           correct_index=1, audio_text="风一更，雪一更，聒碎乡心梦不成。", audio_voice="zh-CN-YunxiNeural"),
    ]

    # ---------------- C3-2 爱国送别与哲理古诗 ----------------
    bank["C3-2"] = [
        _poem_tile_q("c32-1", "C3-2", "basic",
                     "听朗诵并点选字块，补全陆游《示儿》名句：「王师北定中原日，____。」",
                     "家祭无忘告乃翁", ["勿", "奶"],
                     "“家祭无忘告乃翁”表达了陆游临终仍心系国家统一的深沉爱国情。",
                     audio_text="王师北定中原日，家祭无忘告乃翁。", seed=33),
        _poem_tile_q("c32-2", "C3-2", "basic",
                     "听朗诵并点选字块，补全朱熹《观书有感》名句：「问渠那得清如许？____。」",
                     "为有源头活水来", ["原", "火"],
                     "比喻只有不断读书学习补充新知识，思想才不会枯竭。",
                     audio_text="问渠那得清如许？为有源头活水来。", seed=34),
        _q("c32-3", "C3-2", "reading_choice", "medium",
           "龚自珍《己亥杂诗》“我劝天公重抖擞，不拘一格降人材”表达了诗人怎样的愿望？", "期盼朝廷打破常规、广纳贤才以振兴国家",
           "“不拘一格”指不局限于一种规格或方式，抒发了变革图强的爱国热情。",
           options=["希望天降大雨滋润农田", "期盼朝廷打破常规、广纳贤才以振兴国家", "向往隐居山林的清闲生活", "赞美春日百花齐放的景象"],
           correct_index=1, audio_text="我劝天公重抖擞，不拘一格降人材。", audio_voice="zh-CN-YunxiNeural"),
        _q("c32-4", "C3-2", "poem_fill", "medium",
           "听朗诵，直接用键盘精准默写陆游《示儿》前两句中的下句：「死去元知万事空，________。」",
           "但悲不见九州同",
           "注意“九州”不是“九洲”，“但”意为“只是”。",
           hint="7 个汉字", audio_text="死去元知万事空，但悲不见九州同。", audio_voice="zh-CN-YunxiNeural"),
        _q("c32-5", "C3-2", "poem_fill", "hard",
           "听朗诵，直接用键盘精准默写林升《题临安邸》下句：「暖风熏得游人醉，________。」",
           "直把杭州作汴州",
           "“作”不要写成“做”，讽刺南宋权贵沉迷享乐、忘却故土。",
           hint="7 个汉字", audio_text="暖风熏得游人醉，直把杭州作汴州。", audio_voice="zh-CN-YunxiNeural"),
        _q("c32-6", "C3-2", "reading_choice", "hard",
           "“九州生气恃风雷”中“生气”和“恃”的意思分别是：", "朝气蓬勃的局面；依靠",
           "“生气”在这里不是发怒，而是指充满活力的局面；“恃”是依靠的意思。",
           options=["发脾气；等待", "朝气蓬勃的局面；依靠", "生病；保持", "生活气息；害怕"],
           correct_index=1, audio_text="九州生气恃风雷，万马齐喑究可哀。", audio_voice="zh-CN-YunxiNeural"),
    ]

    # ---------------- C3-3 小古文重点实词与句意 ----------------
    bank["C3-3"] = [
        _q("c33-1", "C3-3", "reading_choice", "basic",
           "“敏而好学，不耻下问”中“耻”的意思是：", "以……为耻",
           "意动用法，表示“不以向地位或学问不如自己的人请教为耻”。",
           options=["羞愧流泪", "以……为耻", "停止学习", "嘲笑别人"],
           correct_index=1, audio_text="敏而好学，不耻下问。", audio_voice="zh-CN-YunxiNeural"),
        _q("c33-2", "C3-3", "reading_choice", "basic",
           "“知之为知之，不知为不知，是知也”中最后一个“知”读音和意思是：", "zhì，同“智”，智慧",
           "最后一个“知”是通假字，同“智”，意为真正的智慧。",
           options=["zhī，知道", "zhì，同“智”，智慧", "zhī，认识", "zhì，志向"],
           correct_index=1, audio_text="知之为知之，不知为不知，是知也。", audio_voice="zh-CN-YunxiNeural"),
        _q("c33-3", "C3-3", "reading_choice", "medium",
           "朱熹说读书有“三到”，其中最重要且“既到矣，眼口岂不到乎”的是：", "心到",
           "读书三到为心到、眼到、口到，其中“心到最急（最要紧）”。",
           options=["眼到", "口到", "心到", "手到"],
           correct_index=2, audio_text="余尝谓读书有三到，谓心到、眼到、口到。", audio_voice="zh-CN-YunxiNeural"),
        _q("c33-4", "C3-3", "reading_choice", "medium",
           "“默而识之”中“识”的正确读音和意思是：", "zhì，记住",
           "“识”在此读 zhì，意思是“记住”，整句意为默默地把知识记在心里。",
           options=["shí，认识", "zhì，记住", "shì，知识", "zhī，理解"],
           correct_index=1, audio_text="默而识之，学而不厌，诲人不倦。", audio_voice="zh-CN-YunxiNeural"),
        _q("c33-5", "C3-3", "reading_choice", "hard",
           "“学而不厌，诲人不倦”中“厌”和“诲”的意思分别是：", "满足；教诲",
           "“学而不厌”指学习永不满足；“诲人不倦”指教导别人不知疲倦。",
           options=["讨厌；后悔", "满足；教诲", "厌倦；悔改", "喜欢；询问"],
           correct_index=1),
        _q("c33-6", "C3-3", "poem_fill", "hard",
           "精准默写《论语》中强调虚心向他人请教的八字名句：「________，________。」（中间不加标点或加逗号均可）",
           "敏而好学，不耻下问",
           "“敏而好学，不耻下问”出自《论语》，意为聪敏又勤学，不以向不如自己的人请教为耻。",
           hint="8 个汉字"),
    ]

    # ---------------- C3-4 名言警句与俗语积累 ----------------
    bank["C3-4"] = [
        _poem_tile_q("c34-1", "C3-4", "basic",
                     "点击字块补全惜时名言：「盛年不重来，____。」",
                     "一日难再晨", ["两", "辰"],
                     "陶渊明名句“盛年不重来，一日难再晨”，告诫我们要珍惜青春时光。",
                     audio_text="盛年不重来，一日难再晨。", seed=35),
        _q("c34-2", "C3-4", "reading_choice", "basic",
           "“一粥一饭，当思来处不易”倡导的是哪种传统美德？", "勤俭节约",
           "出自朱用纯《朱子家训》，教导我们珍惜粮食、勤俭节约。",
           options=["诚实守信", "勤俭节约", "见义勇为", "尊师重道"], correct_index=1),
        _q("c34-3", "C3-4", "reading_choice", "medium",
           "岳飞《满江红》中劝诫少年不可虚度光阴、以免年老悔恨的名句是：", "莫等闲，白了少年头，空悲切。",
           "“莫等闲，白了少年头，空悲切”是经典的惜时励志名句。",
           options=["不饱食以终日，不弃功于寸阴。", "莫等闲，白了少年头，空悲切。", "克勤于邦，克俭于家。", "居安思危，戒奢以俭。"],
           correct_index=1),
        _q("c34-4", "C3-4", "poem_fill", "medium",
           "直接用键盘默写关于“居安思危、戒除奢侈”的八字名言：「居安思危，________。」",
           "戒奢以俭",
           "魏征名言“居安思危，戒奢以俭”，注意“奢”和“俭”的写法。",
           hint="4 个汉字"),
        _q("c34-5", "C3-4", "reading_choice", "hard",
           "下面哪句名言最适合用来劝慰“怕花时间、想一口吃成胖子”的同学？", "不饱食以终日，不弃功于寸阴。",
           "葛洪名言强调不虚度光阴、不放弃点滴时间去积累功夫。",
           options=["不饱食以终日，不弃功于寸阴。", "由俭入奢易，由奢入俭难。", "前怕狼后怕虎。", "打开天窗说亮话。"],
           correct_index=0),
        _q("c34-6", "C3-4", "poem_fill", "hard",
           "直接用键盘默写《尚书》中赞美“对国家勤劳、对家庭节俭”的八字名言（下句）：「克勤于邦，________。」",
           "克俭于家",
           "“克勤于邦，克俭于家”意为为国家大事辛勤操劳，在家庭生活里勤俭节约。",
           hint="4 个汉字"),
    ]

    # ---------------- C4-1 抓关键句与概括主要内容 ----------------
    p_narrative = (
        "放学路上突然下起瓢泼大雨，我没带伞，只能站在校门口焦急地张望。"
        "这时，平时总爱和我争论数学题的小周撑着一把蓝伞走过来，二话不说把伞往我这边倾斜了一大半。"
        "一路上，他讲着刚编的冷笑话，逗得我忘了冷。送到我家楼下时，我才发现他右半边肩膀早已被雨水浇透，而他只是笑着挥挥手，转身跑进雨幕里。"
    )
    bank["C4-1"] = [
        _q("c41-1", "C4-1", "reading_choice", "basic",
           "阅读短文，这段话主要讲了一件什么事？", "雨天放学时，小周主动为没带伞的“我”撑伞送回家，自己淋湿了肩膀",
           "概括记叙文主要内容可按“时间/起因 + 人物 + 经过 + 结果”提炼，抓住小周雨中让伞的核心事件。",
           options=["“我”和小周在放学路上争论一道数学题", "雨天放学时，小周主动为没带伞的“我”撑伞送回家，自己淋湿了肩膀", "校门口的蓝伞非常漂亮", "小周讲的冷笑话非常有趣"],
           correct_index=1, passage=p_narrative),
        _q("c41-2", "C4-1", "reading_choice", "basic",
           "快速默读一段话以把握主要意思时，最有效的方法是：", "带着问题连词成句地读，重点抓段落的中心句和关键词",
           "提高阅读速度要避免逐字指读和反复回读，抓住中心句与关键词即可高效把握大意。",
           options=["用手指着每个字出声朗读", "遇到不懂的词立刻停下来查半小时字典", "带着问题连词成句地读，重点抓段落的中心句和关键词", "只看第一句和最后一句，中间全部跳过"],
           correct_index=2),
        _q("c41-3", "C4-1", "reading_choice", "medium",
           "短文中“把伞往我这边倾斜了一大半”“右半边肩膀早已被雨水浇透”体现了小周怎样的品质？", "热心善良、宁愿自己吃亏也要照顾同学",
           "通过动作与结果细节描写，凸显小周处处替别人着想的真诚善良。",
           options=["粗心大意、不会打伞", "热心善良、宁愿自己吃亏也要照顾同学", "喜欢在雨里跑步锻炼", "想让“我”帮他做数学题"],
           correct_index=1, passage=p_narrative),
        _q("c41-4", "C4-1", "reading_choice", "medium",
           "如果要给上面这篇短文起一个最贴切的题目，哪一个最好？", "倾斜的蓝伞",
           "“倾斜的蓝伞”既是贯穿全文的线索物，又含蓄点出了小周关爱同学的主题。",
           options=["一场大雨", "倾斜的蓝伞", "难忘的数学题", "放学以后"],
           correct_index=1, passage=p_narrative),
        _q("c41-5", "C4-1", "reading_short", "hard",
           "【阅读简答】读完短文，为什么说小周“只是笑着挥挥手，转身跑进雨幕里”让“我”特别感动？请结合短文细节写 1～2 句话说明理由。",
           "小周把伞大半倾斜给“我”，自己右肩全被淋湿却毫不在意，还讲笑话安慰“我”、笑着离开，体现了他真诚善良、默默关怀他人的可贵品质。",
           "答题思路：先点明文中具体细节（让伞/淋湿肩膀/讲笑话），再概括人物品质或情感。",
           passage=p_narrative,
           rubric_keywords=[["淋湿", "浇透", "让伞", "倾斜"], ["善良", "热心", "关心", "照顾", "体贴", "不图回报", "真诚"]],
           min_chars=15,
           sample_answer="因为小周一路把伞倾斜给我，自己右肩被雨水浇透却只字不提，还笑着离开，让我感受到他真诚善良、处处为同学着想的美好品质。"),
        _q("c41-6", "C4-1", "reading_choice", "hard",
           "文中特意交代小周“平时总爱和我争论数学题”，这样写的作用是：", "用平时的小争论作铺垫，反衬关键时刻小周对同学的真诚关心",
           "先写日常小摩擦，再写雨中无私让伞，形成对比反衬，人物形象更立体。",
           options=["说明小周数学成绩不好", "凑字数让文章更长", "用平时的小争论作铺垫，反衬关键时刻小周对同学的真诚关心", "引出下文两人继续算题"],
           correct_index=2, passage=p_narrative),
    ]

    # ---------------- C4-2 说明方法与说明文细节 ----------------
    p_expository = (
        "中国空间站的“天和”核心舱全长约 16.6 米，最大直径 4.2 米，发射质量达 22.5 吨，内部活动空间足有 50 立方米，相当于一套温馨的两居室。"
        "在太空中，航天员不仅能在这里开展科学实验，还能像在家里一样加热饭菜、上网通话，甚至通过太空跑台坚持每日锻炼。"
    )
    bank["C4-2"] = [
        _q("c42-1", "C4-2", "reading_choice", "basic",
           "“全长约 16.6 米，最大直径 4.2 米，发射质量达 22.5 吨”主要运用了哪种说明方法？", "列数字",
           "通过精确数据具体准确地介绍核心舱的尺寸与重量，属于“列数字”。",
           options=["打比方", "列数字", "作假设", "引资料"], correct_index=1, passage=p_expository),
        _q("c42-2", "C4-2", "reading_choice", "basic",
           "“内部活动空间足有 50 立方米，相当于一套温馨的两居室”还运用了哪种说明方法？", "作比较（打比方）",
           "将抽象的“50 立方米”与生活中熟悉的“两居室”相比，让读者直观感受到空间宽敞。",
           options=["作比较（打比方）", "下定义", "分类别", "摹状貌"], correct_index=0, passage=p_expository),
        _q("c42-3", "C4-2", "reading_choice", "medium",
           "“全长约 16.6 米”中的“约”字能不能去掉？为什么？", "不能，“约”表示大约、估算，去掉后与事实不符，体现了说明文语言的严谨准确性",
           "说明文语言讲究准确严密，表示估计或限制的词（约、左右、主要、通常）不可随意删除。",
           options=["可以去掉，去掉后句子更简洁", "不能，“约”表示大约、估算，去掉后与事实不符，体现了说明文语言的严谨准确性", "可以去掉，因为 16.6 已经很精确了", "不能，因为去掉后句子变成病句"],
           correct_index=1, passage=p_expository),
        _q("c42-4", "C4-2", "reading_choice", "medium",
           "根据短文内容，航天员在“天和”核心舱里可以做的事情不包括哪一项？", "种植大面积农田",
           "原文提到了科学实验、加热饭菜、上网通话、太空跑台锻炼，未提及种植大面积农田。",
           options=["开展科学实验", "加热饭菜和上网通话", "通过太空跑台锻炼", "种植大面积农田"],
           correct_index=3, passage=p_expository),
        _q("c42-5", "C4-2", "reading_short", "hard",
           "【阅读简答】作者为什么把核心舱 50 立方米的活动空间说成“相当于一套温馨的两居室”？这样写有什么好处？",
           "运用作比较/打比方的说明方法，把抽象的空间大小与人们熟悉的两居室对比，生动直观地写出核心舱内部空间的宽敞与舒适。",
           "说明方法作用答题模板：点明说明方法 + 结合内容说明写出了事物的什么特点 + 表达效果（准确/直观/生动）。",
           passage=p_expository,
           rubric_keywords=[["比较", "比方", "对比", "熟悉"], ["直观", "生动", "清楚", "明白"], ["宽敞", "大", "舒适", "温馨"]],
           min_chars=15,
           sample_answer="作者运用作比较的说明方法，把抽象的50立方米和大家熟悉的两居室对比，生动直观地写出了核心舱内部空间的宽敞与舒适。"),
        _q("c42-6", "C4-2", "reading_choice", "hard",
           "下列句子中同时运用了“列数字”和“作比较”两种说明方法的是：", "太阳离我们约有一亿五千万千米远，到太阳上去，如果步行，日夜不停地走，差不多要走三千五百年。",
           "不仅列出了具体数字，还通过步行耗时与太阳距离作比较，突出太阳距离地球极远。",
           options=["鲸的种类很多，总的来说可以分为两大类：一类是须鲸，一类是齿鲸。", "太阳像一个大火球，照亮了大地。", "太阳离我们约有一亿五千万千米远，到太阳上去，如果步行，日夜不停地走，差不多要走三千五百年。", "松鼠是一种漂亮的小动物，乖巧，驯良，很讨人喜欢。"],
           correct_index=2),
    ]

    # ---------------- C4-3 人物描写与情感体会 ----------------
    bank["C4-3"] = [
        _q("c43-1", "C4-3", "reading_choice", "basic",
           "“母亲掏衣兜，掏出一卷揉得皱皱的毛票，用龟裂的手指数着。”这句话主要运用了什么描写？", "动作描写和细节描写",
           "“掏”“数”是动作描写，“皱皱的毛票”“龟裂的手指”是极具感染力的细节描写，表现母亲挣钱艰辛。",
           options=["语言描写", "心理描写", "动作描写和细节描写", "环境描写"], correct_index=2),
        _q("c43-2", "C4-3", "reading_choice", "basic",
           "通过“皱皱的毛票”和“龟裂的手指”，我们最能体会到：", "母亲平日劳作的艰辛与对孩子无私的爱",
           "细节描写往往“以小见大”，折射出母亲的辛劳与深沉的母爱。",
           options=["母亲不喜欢整理口袋", "母亲平日劳作的艰辛与对孩子无私的爱", "冬天的天气非常干燥", "书店里的书太贵了"],
           correct_index=1),
        _q("c43-3", "C4-3", "reading_choice", "medium",
           "“他涨红了脸，低下头搓着衣角，小声嘟囔道：‘对不起，是我不小心碰倒了花盆。’”展现了人物怎样的心理？", "愧疚、紧张但勇于承认错误",
           "神态（涨红脸）、动作（低头搓衣角）与语言（小声道歉）共同刻画了既羞愧又诚实的心理。",
           options=["得意洋洋", "愤怒不满", "愧疚、紧张但勇于承认错误", "毫不在乎"], correct_index=2),
        _q("c43-4", "C4-3", "reading_choice", "medium",
           "下列哪一句把“焦急”写得最具体生动（把画面写具体）？", "他在站台上来回踱步，每隔半分钟就抬腕看一次手表，眉头拧成了一个结。",
           "不直接空喊“他很焦急”，而是通过踱步、看表、皱眉等动作神态把“焦急”演出来。",
           options=["他站在那里非常非常焦急。", "他焦急得不得了，心里急死了。", "他在站台上来回踱步，每隔半分钟就抬腕看一次手表，眉头拧成了一个结。", "他等了很长时间车还没来。"],
           correct_index=2),
        _q("c43-5", "C4-3", "micro_writing", "hard",
           "【微片段写作】请不要直接出现“紧张”二字，用 60～120 字的动作、神态或心理细节，写出一位同学「上台演讲前非常紧张」的画面。",
           "动作、神态、心理细节描写完整，不直接空喊“紧张”，画面感强。",
           "写作锦囊：抓住手心出汗、捏紧演讲稿、心跳加速、深呼吸等具体细节来“演”出紧张。",
           rubric_keywords=[["手", "汗", "握", "捏", "抖"], ["心跳", "呼吸", "扑通", "嗓子", "脸", "眼"]],
           min_chars=35,
           sample_answer="候场区里，我紧紧攥着手里的演讲稿，纸角早已被手心的汗水浸得发软。胸口像揣了一只受惊的小兔子，“扑通扑通”撞个不停。听到主持人念出我的名字，我深吸一口气，微微发抖着迈上了台阶。"),
        _q("c43-6", "C4-3", "reading_choice", "hard",
           "“父爱之舟”中作者反复写到姑爹的小渔船，这种写作手法叫做：", "借物抒情（以小渔船为线索寄托对父亲的怀念）",
           "小渔船串联起父亲送考、缝补棉被等成长片段，是典型的以物为线索、借物抒情。",
           options=["借物抒情（以小渔船为线索寄托对父亲的怀念）", "欲扬先抑", "首尾无关", "纯说明介绍"],
           correct_index=0),
    ]

    # ---------------- C4-4 审题立意与细节升格 ----------------
    bank["C4-4"] = [
        _q("c44-1", "C4-4", "reading_choice", "basic",
           "作文题《漫画老师》的写作重点应该是：", "抓住老师最鲜明的外貌、性格特点，用 1～2 件具体事例把特点写活",
           "“漫画”意味着突出最鲜明的特征，并配合典型事例让人物跃然纸上。",
           options=["把老师从早到晚上的每一节课流水账式记下来", "抓住老师最鲜明的外貌、性格特点，用 1～2 件具体事例把特点写活", "只夸老师很好，不需要写具体事件", "介绍学校里所有老师的名字"],
           correct_index=1),
        _q("c44-2", "C4-4", "reading_choice", "basic",
           "如果要把“夕阳很美”升格为更生动的写景句，下面哪一句效果最好？", "夕阳把云霞染成了橘红色，连波光粼粼的湖面也仿佛铺上了一层碎金。",
           "调动色彩词（橘红、碎金）与比喻、动态（波光粼粼），让静态景物鲜活起来。",
           options=["今天的夕阳真的太美太美了。", "夕阳挂在西边的天空中，很好看。", "夕阳把云霞染成了橘红色，连波光粼粼的湖面也仿佛铺上了一层碎金。", "太阳快要落山了，天边有夕阳。"],
           correct_index=2),
        _q("c44-3", "C4-4", "reading_choice", "medium",
           "作文题《二十年后的家乡》属于想象作文，为了让文章有条理、不空洞，最合理的提纲是：", "分段列出环境、交通、生活 2～3 个方面的具体变化，重点详写其中最精彩的一处场景",
           "先搭清晰提纲、确定详略（重点场景细写，其余略写），文章才会结构分明。",
           options=["把能想到的高科技名词全部堆在第一段", "分段列出环境、交通、生活 2～3 个方面的具体变化，重点详写其中最精彩的一处场景", "只写今天家乡的样子，最后一句说二十年后会更好", "不需要分段，一口气写完"],
           correct_index=1),
        _q("c44-4", "C4-4", "reading_choice", "medium",
           "写《介绍一种事物》（如扫地机器人或家乡美食）时，下面哪种开头最能吸引读者？", "用一个有趣的问题或生活场景引出说明对象，再分方面运用说明方法介绍",
           "情境设问式开头既自然引出说明对象，又激发阅读兴趣。",
           options=["今天我要介绍一样东西，请大家听我慢慢说。", "用一个有趣的问题或生活场景引出说明对象，再分方面运用说明方法介绍", "直接把说明书一字不差抄下来", "只写“我非常喜欢它”，不介绍特点"],
           correct_index=1),
        _q("c44-5", "C4-4", "micro_writing", "hard",
           "【微片段写作】请把「校园里的桂花开了，很香」扩写升格为 60～120 字的动态写景片段，至少运用一种修辞手法（比喻或拟人），调动视觉与嗅觉描写。",
           "结合视觉、嗅觉与比喻/拟人修辞，把静态景物写活。",
           "写作锦囊：写花朵的样子（像米粒/金星）、微风吹过时的动态，以及香气如何飘进教室。",
           rubric_keywords=[["桂花", "花", "枝", "叶"], ["香", "甜", "味", "飘"], ["像", "仿佛", "犹如", "钻", "招手", "笑", "眨眼", "跳舞"]],
           min_chars=35,
           sample_answer="秋风轻轻拂过，校园里的桂花悄悄绽放了。米粒般大小的淡黄色花朵躲在翠绿的叶间，像缀满了无数颗闪亮的小星星。一阵清风吹来，甜甜的幽香调皮地钻进教室的窗户，让正在读书的我们瞬间神清气爽。"),
        _q("c44-6", "C4-4", "reading_choice", "hard",
           "写记事作文的结尾时，哪种写法最能让文章“余味悠长”？", "点明这件事带给自己的成长感悟或呼应开头场景，自然升华主题",
           "首尾呼应或点题升华能把具体事件与情感感悟紧密扣合。",
           options=["写一句“这就是今天发生的事，写完了”", "点明这件事带给自己的成长感悟或呼应开头场景，自然升华主题", "突然引入一个全新的、前文没提过的人物", "把第一段原封不动再抄一遍"],
           correct_index=1),
    ]

    return bank


QUESTION_BANK = _build_question_bank()


def collect_audio_specs() -> list[dict[str, str]]:
    """收集题库中全部需要离线生成的普通话 MP3 音频（按 audioId 去重）."""
    seen: dict[str, dict[str, str]] = {}
    for qs in QUESTION_BANK.values():
        for q in qs:
            aid = q.get("audioId")
            txt = q.get("audioText")
            if aid and txt and aid not in seen:
                seen[aid] = {
                    "audioId": aid,
                    "text": txt,
                    "voice": q.get("audioVoice", "zh-CN-XiaoxiaoNeural"),
                }
    return list(seen.values())


def get_map_blueprint() -> dict[str, Any]:
    return {
        "subject": SUBJECT_CHINESE,
        "grade": DEFAULT_GRADE,
        "domains": [dict(d) for d in CHINESE_G5_DOMAINS],
        "nodes": [dict(n) for n in CHINESE_G5_NODES],
    }


def generate_node_questions(
    node_key: str,
    *,
    count: int = 5,
    seed: int = 0,
    exclude_ids: Iterable[str] = (),
    types: set[str] | None = None,
    map_friendly: bool = False,
) -> list[dict[str, Any]]:
    pool = QUESTION_BANK.get(node_key)
    if not pool:
        raise ValueError(f"Unknown Chinese node: {node_key}")
    excluded = set(exclude_ids)
    filtered = [q for q in pool if q["id"] not in excluded]
    if types:
        filtered = [q for q in filtered if q["questionType"] in types]
    elif map_friendly:
        friendly = [q for q in filtered if q["questionType"] in MAP_FRIENDLY_TYPES]
        if len(friendly) >= count:
            filtered = friendly
        else:
            rest = [q for q in filtered if q not in friendly]
            filtered = friendly + rest
    if not filtered:
        return []
    n = len(filtered)
    shift = abs(int(seed)) % n
    ordered = filtered[shift:] + filtered[:shift]
    return [copy.deepcopy(q) for q in ordered[:count]]


def public_question(q: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id", "nodeKey", "questionType", "typeLabel", "level", "levelLabel",
        "marks", "text", "options", "audioId", "audioUrl", "hint",
        "tiles", "passage", "minChars",
    )
    return {k: copy.deepcopy(q[k]) for k in keep if k in q}


def _strip_cn_punct(s: str) -> str:
    return re.sub(r"[\s，。！？、；：“”‘’\"',.!?;:（）()《》\-—]", "", str(s or "").strip())


def grade_objective_answer(
    question: dict[str, Any],
    *,
    selected_index: int | None = None,
    text_answer: str = "",
) -> bool:
    """判分全部客观题、字块拼词、听写拼词、古诗精准默写与病句找茬."""
    qt = question.get("questionType", "")
    ans = str(question.get("answer", ""))
    if qt in ("basic_choice", "error_spot", "sentence_choice", "reading_choice"):
        if selected_index is None:
            return False
        return int(selected_index) == int(question.get("correctIndex", -1))

    got = _strip_cn_punct(text_answer)
    if not got:
        return False
    expected = _strip_cn_punct(ans)
    return got == expected


def grade_subjective_rule_fallback(question: dict[str, Any], text_answer: str) -> dict[str, Any]:
    """本地规则兜底评分（当未配置大模型 API Key 或超时时无缝启用）."""
    max_marks = int(question.get("marks", TYPE_POINTS.get(question.get("questionType", ""), 4)))
    raw = str(text_answer or "").strip()
    clean_len = len(_strip_cn_punct(raw))
    min_chars = int(question.get("minChars", 12))
    groups: list[list[str]] = question.get("rubricKeywords") or []

    if clean_len < max(6, min_chars // 3):
        return {
            "earnedMarks": 0,
            "maxMarks": max_marks,
            "passed": False,
            "gradingMode": "rule_fallback",
            "comment": f"作答内容过短（当前 {clean_len} 字），请结合题干要求补充完整内容后再提交。",
        }

    hit_groups = 0
    for g in groups:
        if any(kw in raw for kw in g):
            hit_groups += 1

    ratio = (hit_groups / len(groups)) if groups else 0.7
    len_bonus = 0.2 if clean_len >= min_chars else 0.0
    score_ratio = min(1.0, ratio * 0.8 + len_bonus)
    earned = int(round(max_marks * score_ratio))
    if clean_len >= min_chars and hit_groups >= 1:
        earned = max(earned, max(1, max_marks // 2))
    passed = earned >= max(1, int(round(max_marks * 0.6)))

    if passed:
        comment = f"表达较完整（{clean_len} 字），命中了 {hit_groups}/{len(groups)} 项核心要点；可对照范文进一步打磨细节用词。"
    else:
        comment = f"已作答 {clean_len} 字，但关键得分要素覆盖不足（命中 {hit_groups}/{len(groups)} 项），建议参考下方答题思路与范文补充关键细节。"
    return {
        "earnedMarks": earned,
        "maxMarks": max_marks,
        "passed": passed,
        "gradingMode": "rule_fallback",
        "comment": comment,
    }


def compute_light_state(
    *,
    attempts: int,
    correct: int,
    hard_correct: int,
    best_quiz_rate_pct: int,
    sprint_boost_stars: int,
    needs_repair: bool,
) -> dict[str, Any]:
    stars = 0
    state = "unexplored"
    if attempts > 0 or sprint_boost_stars > 0:
        state = "exploring"
    if best_quiz_rate_pct >= 80 or sprint_boost_stars >= 1:
        state = "lit"
        stars = max(1, min(3, sprint_boost_stars or 1))
    if (best_quiz_rate_pct >= 100 and hard_correct >= 1) or sprint_boost_stars >= 3 or (best_quiz_rate_pct >= 80 and correct >= 8):
        state = "mastered"
        stars = 3
    elif state == "lit" and (best_quiz_rate_pct >= 90 or sprint_boost_stars >= 2):
        stars = max(stars, 2)
    return {
        "state": state,
        "stateLabel": LIGHT_STATES[state],
        "stars": stars,
        "needsRepair": bool(needs_repair),
    }


__all__ = [
    "CHINESE_G5_DOMAINS",
    "CHINESE_G5_NODES",
    "DEFAULT_GRADE",
    "DOMAIN_BY_ID",
    "LEVEL_LABELS",
    "LIGHT_STATES",
    "MAP_FRIENDLY_TYPES",
    "NODE_BY_KEY",
    "QUESTION_BANK",
    "SUBJECTIVE_TYPES",
    "SUBJECT_CHINESE",
    "TYPE_LABELS",
    "TYPE_POINTS",
    "collect_audio_specs",
    "compute_light_state",
    "generate_node_questions",
    "get_map_blueprint",
    "grade_objective_answer",
    "grade_subjective_rule_fallback",
    "make_audio_id",
    "public_question",
]
