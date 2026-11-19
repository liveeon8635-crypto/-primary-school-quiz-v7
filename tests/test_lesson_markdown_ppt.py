from changying.services import lesson_markdown


def test_markdown_lesson_keeps_big_screen_knowledge_pages():
    plan = lesson_markdown.parse(
        """# 第12课：梯形面积
## 本节目标
理解梯形面积公式。
## 教学流程
先拼合，再计算。
## 知识点
先找平行的上底和下底。
高必须与底垂直。
## 例题
1. 上底4厘米、下底8厘米、高6厘米，求面积。
【答案】36平方厘米。
## 课后练习
1. 上底2厘米、下底5厘米、高4厘米，求面积。
【答案】14平方厘米。
"""
    )

    assert plan["ppt"] == ["先找平行的上底和下底。", "高必须与底垂直。"]
    assert plan["teacherPlan"] == "先拼合，再计算。"
    assert len(plan["examples"]) == 1
    assert len(plan["writtenQuestions"]) == 1
