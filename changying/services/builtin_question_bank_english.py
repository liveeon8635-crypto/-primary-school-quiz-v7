"""Grade 5 English (PEP current edition) baseline question pack.

The six unit titles follow the current People's Education Press Grade 5 first
semester PEP line.  All stems, dialogues and mini-passages below are original.
The baseline pack deliberately avoids copied textbook passages and audio-only
tasks so every item can be completed in the existing web quiz flow.
"""

from __future__ import annotations

from typing import Any


ENGLISH_G5_TEXTBOOK = "人教版（PEP·当前最新版）"


def _spec(
    *,
    unit: str,
    knowledge: str,
    text: str,
    answer: str,
    distractors: list[str],
    explanation: str,
    seed: int,
) -> dict[str, Any]:
    answer = str(answer)
    unique: list[str] = []
    for value in distractors:
        value = str(value)
        if value != answer and value not in unique:
            unique.append(value)
    for fallback in ("I don't know.", "Maybe.", "No.", "None of them."):
        if len(unique) >= 3:
            break
        if fallback != answer and fallback not in unique:
            unique.append(fallback)
    options = unique[:3]
    correct_index = seed % 4
    options.insert(correct_index, answer)
    return {
        "grade": 5,
        "subject": "英语",
        "textbook": ENGLISH_G5_TEXTBOOK,
        "semester": "上册",
        "unit": unit,
        "knowledge": knowledge,
        "text": text,
        "options": options,
        "correct_index": correct_index,
        "explanation": explanation,
    }


def _add(
    rows: list[dict[str, Any]],
    *,
    unit: str,
    knowledge: str,
    items: list[tuple[str, str, list[str]]],
    explanation: str,
    seed_offset: int = 0,
) -> None:
    for i, (text, answer, distractors) in enumerate(items):
        rows.append(
            _spec(
                unit=unit,
                knowledge=knowledge,
                text=text,
                answer=answer,
                distractors=distractors,
                explanation=explanation,
                seed=i + seed_offset,
            )
        )


def grade5_english_specs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    u1 = "Unit 1 · Different friends"
    _add(
        rows,
        unit=u1,
        knowledge="人物特征词汇",
        items=[
            ('Which word means “友善的”?', "kind", ["angry", "tired", "empty"]),
            ('Which word means “乐于助人的”?', "helpful", ["thirsty", "cloudy", "salty"]),
            ('Which word means “安静的”?', "quiet", ["hungry", "busy", "sweet"]),
            ('Which word means “有趣的；滑稽的”?', "funny", ["heavy", "wet", "sour"]),
            ('Which word means “聪明的”?', "clever", ["cold", "slow", "round"]),
            ('Which word means “有礼貌的”?', "polite", ["noisy", "spicy", "dirty"]),
            ('Which word means “勤奋的”?', "hard-working", ["lazy", "rainy", "high"]),
            ('Which word means “害羞的”?', "shy", ["strong", "expensive", "full"]),
        ],
        explanation="根据人物特征形容词的常用含义选择正确答案。",
    )
    _add(
        rows,
        unit=u1,
        knowledge="人物信息理解",
        items=[
            ("Lina always helps new students find their classrooms. What is Lina like?", "She is helpful.", ["She is hungry.", "She is cloudy.", "She is sour."]),
            ("Eric studies carefully and finishes every task on time. What is Eric like?", "He is hard-working.", ["He is thirsty.", "He is empty.", "He is rainy."]),
            ("Nora says “please” and “thank you” to everyone. What is Nora like?", "She is polite.", ["She is wet.", "She is spicy.", "She is noisy."]),
            ("Sam makes the class laugh with funny stories. What is Sam like?", "He is funny.", ["He is salty.", "He is square.", "He is cloudy."]),
            ("Mia speaks softly and does not talk much with strangers. What is Mia like?", "She is shy.", ["She is sweet.", "She is tall.", "She is hungry."]),
            ("Leo solves new puzzles very quickly. What is Leo like?", "He is clever.", ["He is cold.", "He is sour.", "He is wet."]),
            ("Ms Chen listens patiently and never shouts at students. What is she like?", "She is kind.", ["She is bitter.", "She is heavy.", "She is windy."]),
            ("The reading room is calm, and Ben always speaks softly there. What is Ben like?", "He is quiet.", ["He is spicy.", "He is rainy.", "He is empty."]),
        ],
        explanation="根据短句中的行为线索判断人物特征。",
        seed_offset=1,
    )
    _add(
        rows,
        unit=u1,
        knowledge="人物描述句型",
        items=[
            ("Choose the correct sentence.", "She is kind.", ["She are kind.", "She be kind.", "She am kind."]),
            ("Choose the correct sentence.", "They are helpful.", ["They is helpful.", "They am helpful.", "They be helpful."]),
            ("—What is your new friend like? —____", "He is quiet and polite.", ["He like basketball.", "He is in Grade Five.", "He has Monday."]),
            ("—What are Lily and May like? —____", "They are friendly.", ["They is friendly.", "They are friend.", "They friendly are."]),
            ("Tom and I ____ good friends.", "are", ["is", "am", "be"]),
            ("My English teacher ____ very patient.", "is", ["are", "am", "be"]),
            ("I ____ shy when I meet new people.", "am", ["is", "are", "be"]),
            ("Which question asks about a person's character?", "What is she like?", ["What does she like?", "Where is she?", "How old is the room?"]),
        ],
        explanation="根据主语选择正确的 be 动词，并区分 What is ... like? 的人物描述功能。",
        seed_offset=2,
    )

    u2 = "Unit 2 · My feelings"
    _add(
        rows,
        unit=u2,
        knowledge="情绪词汇",
        items=[
            ('Which word means “开心的”?', "happy", ["angry", "worried", "tired"]),
            ('Which word means “伤心的”?', "sad", ["excited", "proud", "calm"]),
            ('Which word means “生气的”?', "angry", ["glad", "quiet", "kind"]),
            ('Which word means “担心的”?', "worried", ["funny", "polite", "helpful"]),
            ('Which word means “兴奋的”?', "excited", ["sleepy", "sad", "angry"]),
            ('Which word means “疲倦的”?', "tired", ["clever", "fresh", "young"]),
            ('Which word means “害怕的”?', "afraid", ["healthy", "busy", "sweet"]),
            ('Which word means “平静的”?', "calm", ["spicy", "hungry", "noisy"]),
        ],
        explanation="辨认常见情绪形容词。",
    )
    _add(
        rows,
        unit=u2,
        knowledge="情绪原因与建议",
        items=[
            ("Amy lost her favourite pencil. How may she feel?", "She may feel sad.", ["She may feel excited.", "She may feel full.", "She may feel funny."]),
            ("Ben will give a speech in five minutes and keeps checking his notes. How may he feel?", "He may feel worried.", ["He may feel sweet.", "He may feel empty.", "He may feel tall."]),
            ("Lucy won the school running race. How may she feel?", "She may feel excited.", ["She may feel angry.", "She may feel sleepy.", "She may feel sour."]),
            ("Tom stayed up too late last night. How may he feel this morning?", "He may feel tired.", ["He may feel spicy.", "He may feel polite.", "He may feel round."]),
            ("Jack hears a very loud noise outside at night. How may he feel?", "He may feel afraid.", ["He may feel healthy.", "He may feel fresh.", "He may feel clever."]),
            ("Your friend is angry. Which advice is best?", "Take a slow breath and talk calmly.", ["Shout louder.", "Throw the book.", "Run across the road."]),
            ("Your classmate feels sad after making a mistake. What can you say?", "It's OK. We can try again.", ["Never speak to me.", "You must be perfect.", "Go away now."]),
            ("You feel worried before a test. What is a helpful choice?", "Review the key points and rest well.", ["Do not sleep all night.", "Skip every question.", "Hide the test paper."]),
        ],
        explanation="根据情境判断合理情绪，并选择恰当的自我调节或同伴支持方式。",
        seed_offset=1,
    )

    u3 = "Unit 3 · Work and play"
    _add(
        rows,
        unit=u3,
        knowledge="学习与活动词组",
        items=[
            ('Which phrase means “做家庭作业”?', "do homework", ["play breakfast", "read football", "make Sunday"]),
            ('Which phrase means “读书”?', "read books", ["cook books", "drink books", "play books"]),
            ('Which phrase means “踢足球”?', "play football", ["do football", "read football", "make football"]),
            ('Which phrase means “打扫房间”?', "clean the room", ["drink the room", "read the room", "play the room"]),
            ('Which phrase means “帮助父母”?', "help parents", ["draw parents", "eat parents", "play parents"]),
            ('Which phrase means “参加体育运动”?', "play sports", ["do a river", "make Monday", "read tea"]),
            ('Which phrase means “练习英语”?', "practise English", ["drink English", "cook English", "sleep English"]),
            ('Which phrase means “和朋友一起玩”?', "play with friends", ["work a lake", "read a bridge", "eat a week"]),
        ],
        explanation="辨认学习、劳动和休闲活动的常用英语表达。",
    )
    _add(
        rows,
        unit=u3,
        knowledge="一般现在时",
        items=[
            ("I ____ my homework after dinner.", "do", ["does", "doing", "am do"]),
            ("She ____ books every evening.", "reads", ["read", "reading", "is read"]),
            ("Tom ____ football on Fridays.", "plays", ["play", "playing", "is play"]),
            ("We ____ the classroom together.", "clean", ["cleans", "cleaning", "is clean"]),
            ("My brother ____ his parents at home.", "helps", ["help", "helping", "are help"]),
            ("They ____ sports after school.", "play", ["plays", "playing", "is play"]),
            ("Does Mia read every day?", "Yes, she does.", ["Yes, she do.", "Yes, she is.", "Yes, she can reads."]),
            ("Do you help at home?", "Yes, I do.", ["Yes, I am.", "Yes, I does.", "Yes, I helping."]),
        ],
        explanation="一般现在时中，第三人称单数谓语通常加 -s/-es；一般疑问句用 do/does。",
        seed_offset=1,
    )
    _add(
        rows,
        unit=u3,
        knowledge="日程信息理解",
        items=[
            ("Monday: reading club. Tuesday: basketball. What does Ken do on Tuesday?", "He plays basketball.", ["He reads in the club.", "He cooks lunch.", "He visits a lake."]),
            ("Lily does homework at 7:00 and reads at 8:00. What does she do first?", "She does homework.", ["She reads.", "She sleeps.", "She plays football."]),
            ("Ben helps his parents every Saturday morning. When does he help them?", "On Saturday morning.", ["On Monday night.", "On Sunday afternoon.", "On Friday noon."]),
            ("The art club meets on Wednesday. Which day should Anna go to the art club?", "Wednesday.", ["Monday.", "Friday.", "Sunday."]),
            ("Leo plays sports after school, then he has dinner. What happens before dinner?", "He plays sports.", ["He sleeps.", "He goes shopping.", "He reads at midnight."]),
            ("Mia has piano practice twice a week: Tuesday and Thursday. How many times a week?", "Twice.", ["Once.", "Three times.", "Every day."]),
            ("On Sunday, Jack rests in the morning and visits his grandparents in the afternoon. When does he visit them?", "Sunday afternoon.", ["Sunday morning.", "Monday afternoon.", "Saturday night."]),
            ("Sara studies from Monday to Friday and relaxes on Saturday. Which day is her rest day?", "Saturday.", ["Tuesday.", "Thursday.", "Friday."]),
        ],
        explanation="从简短日程中提取日期、时间、先后顺序和频率信息。",
        seed_offset=2,
    )

    u4 = "Unit 4 · Healthy habits"
    _add(
        rows,
        unit=u4,
        knowledge="健康习惯词汇",
        items=[
            ('Which phrase means “早睡”?', "go to bed early", ["eat too much sugar", "skip breakfast", "sit all day"]),
            ('Which phrase means “每天锻炼”?', "exercise every day", ["stay up late", "drink no water", "watch all night"]),
            ('Which phrase means “吃早餐”?', "have breakfast", ["miss breakfast", "sleep breakfast", "read breakfast"]),
            ('Which phrase means “喝足够的水”?', "drink enough water", ["eat enough books", "play enough desks", "sleep enough tea"]),
            ('Which is a healthy habit?', "Wash your hands before eating.", ["Never brush your teeth.", "Stay up every night.", "Eat only candy."]),
            ('Which is an unhealthy habit?', "Going to bed very late every night.", ["Walking after dinner.", "Eating vegetables.", "Drinking water."]),
            ('Which habit helps protect your teeth?', "Brush your teeth twice a day.", ["Eat candy before sleep.", "Never rinse your mouth.", "Drink only soda."]),
            ('Which habit helps you stay active?', "Move and exercise regularly.", ["Sit all day.", "Sleep in class.", "Skip all meals."]),
        ],
        explanation="辨认常见健康与不健康生活习惯。",
    )
    _add(
        rows,
        unit=u4,
        knowledge="should与shouldn't",
        items=[
            ("You are very tired. You ____ go to bed earlier.", "should", ["shouldn't", "can't to", "does"]),
            ("You have a toothache. You ____ eat lots of candy.", "shouldn't", ["should", "are", "do"]),
            ("We ____ wash our hands before meals.", "should", ["shouldn't", "is", "does"]),
            ("You want to stay healthy. You ____ exercise regularly.", "should", ["shouldn't", "are not", "has"]),
            ("It is midnight. Children ____ keep playing video games.", "shouldn't", ["should", "do", "are"]),
            ("Your friend is thirsty after PE. What should he do?", "He should drink water.", ["He should skip water.", "He should eat only candy.", "He should stay awake all night."]),
            ("You have a cold. Which advice is sensible?", "You should rest and drink water.", ["You should run outside all night.", "You should eat no food for days.", "You should shout loudly."]),
            ("Which sentence is correct?", "We shouldn't skip breakfast.", ["We shouldn't skipping breakfast.", "We shouldn't skips breakfast.", "We not should breakfast."]),
        ],
        explanation="should 后接动词原形；shouldn't 表示不应该做某事。",
        seed_offset=1,
    )
    _add(
        rows,
        unit=u4,
        knowledge="频率与习惯表达",
        items=[
            ('Which word means “总是”?', "always", ["never", "sometimes", "yesterday"]),
            ('Which word means “经常”?', "often", ["never", "tomorrow", "inside"]),
            ('Which word means “有时”?', "sometimes", ["always", "never", "between"]),
            ('Which word means “从不”?', "never", ["often", "always", "usually"]),
            ("I ____ drink water after PE. It happens almost every time.", "usually", ["never", "yesterday", "under"]),
            ("Nina exercises on Monday, Wednesday and Friday. Which sentence fits best?", "She often exercises.", ["She never exercises.", "She is a river.", "She exercise yesterday every day."]),
            ("Ben never eats breakfast. Which is true?", "He does not eat breakfast at all.", ["He eats breakfast every day.", "He always has two breakfasts.", "He eats breakfast twice an hour."]),
            ("Which sentence is correct?", "I sometimes walk to school.", ["I walk sometimes to school always.", "I sometimes walks to school.", "I am sometimes walk school."]),
        ],
        explanation="理解 always/usually/often/sometimes/never 等频率副词及其在句中的基本位置。",
        seed_offset=2,
    )

    u5 = "Unit 5 · Food we eat"
    _add(
        rows,
        unit=u5,
        knowledge="食物与饮品词汇",
        items=[
            ('Which word means “面条”?', "noodles", ["bridge", "forest", "week"]),
            ('Which word means “米饭”?', "rice", ["river", "clock", "quiet"]),
            ('Which word means “蔬菜”?', "vegetables", ["feelings", "friends", "mountains"]),
            ('Which word means “水果”?', "fruit", ["homework", "Tuesday", "helpful"]),
            ('Which word is a drink?', "milk", ["bread", "rice", "eggs"]),
            ('Which word is a food?', "bread", ["water", "juice", "tea"]),
            ('Which pair contains two drinks?', "milk and water", ["rice and bread", "eggs and noodles", "fruit and vegetables"]),
            ('Which pair contains two foods?', "rice and vegetables", ["water and tea", "juice and milk", "water and juice"]),
        ],
        explanation="辨认常见食物和饮品词汇。",
    )
    _add(
        rows,
        unit=u5,
        knowledge="饮食选择与表达",
        items=[
            ("—What would you like for lunch? —____", "I'd like rice and vegetables.", ["I am Tuesday.", "I can a river.", "There is happy."]),
            ("—Would you like some milk? —____", "Yes, please.", ["Yes, I do milk.", "Yes, I am.", "Yes, there are."]),
            ("—Do you want some fruit? —____", "Yes, please.", ["Yes, I is.", "Yes, I does.", "Yes, fruit can."]),
            ("Which is the healthiest lunch?", "Rice, vegetables, eggs and water.", ["Candy and soda only.", "Only chips.", "No food and no water."]),
            ("Mia doesn't eat meat. Which lunch suits her best?", "Rice, vegetables and tofu.", ["Beef only.", "Chicken and beef.", "Pork only."]),
            ("Ben is thirsty after running. What is a sensible choice?", "Water.", ["A plate.", "A pencil.", "A football."]),
            ("Which sentence is correct?", "I'd like some noodles.", ["I'd noodles like some.", "I would some noodles.", "I like would noodles."]),
            ("Which question asks about a food choice?", "What would you like to eat?", ["How are you feeling?", "What is your friend like?", "When do you play football?"]),
        ],
        explanation="使用 would like / want 等表达饮食需求，并根据简单情境做合理选择。",
        seed_offset=1,
    )

    u6 = "Unit 6 · Nature and us"
    _add(
        rows,
        unit=u6,
        knowledge="自然环境词汇",
        items=[
            ('Which word means “森林”?', "forest", ["bottle", "homework", "feeling"]),
            ('Which word means “河流”?', "river", ["friend", "breakfast", "pencil"]),
            ('Which word means “湖泊”?', "lake", ["week", "room", "milk"]),
            ('Which word means “高山”?', "mountain", ["noodles", "teacher", "Tuesday"]),
            ('Which word means “村庄”?', "village", ["exercise", "angry", "rice"]),
            ('Which word means “桥”?', "bridge", ["quiet", "fruit", "Saturday"]),
            ("Many trees grow together in a large area. It is a ____.", "forest", ["bridge", "bottle", "classroom"]),
            ("Water flows through the land in a long natural channel. It is a ____.", "river", ["mountain", "village", "clock"]),
        ],
        explanation="辨认常见自然环境词汇。",
    )
    _add(
        rows,
        unit=u6,
        knowledge="自然场景信息理解",
        items=[
            ("There is a lake beside the hill. Where is the lake?", "Beside the hill.", ["Under the classroom.", "Inside a pencil.", "On Monday."]),
            ("A bridge goes across the river. What is under the bridge?", "The river.", ["A week.", "A feeling.", "A breakfast."]),
            ("The village is between the forest and the lake. Where is the village?", "Between the forest and the lake.", ["In a bottle.", "After Friday.", "Under homework."]),
            ("There are many birds in the forest. What can you find there?", "Many birds.", ["Many desks.", "Many buses in a classroom.", "Many Mondays."]),
            ("The sign says, “Keep the river clean.” What should visitors do?", "Do not throw rubbish into the river.", ["Throw bottles into the water.", "Wash paint brushes in the river.", "Leave plastic bags on the bank."]),
            ("There is a small path up the mountain. Where does the path go?", "Up the mountain.", ["Into a notebook.", "Across Tuesday.", "Under breakfast."]),
            ("The lake is calm and clean. Which statement matches?", "The water is not dirty.", ["The lake is a classroom.", "The water is full of rubbish.", "The lake is a week."]),
            ("The forest is home to many animals. What does this mean?", "Many animals live there.", ["Animals study maths there.", "The forest is a drink.", "Only cars live there."]),
        ],
        explanation="从原创自然场景短句中提取地点、关系和关键信息。",
        seed_offset=1,
    )
    _add(
        rows,
        unit=u6,
        knowledge="保护自然与行为判断",
        items=[
            ("Which action helps protect a park?", "Put rubbish in the bin.", ["Leave plastic on the grass.", "Break young trees.", "Write on rocks."]),
            ("Which action saves water?", "Turn off the tap after washing.", ["Let the tap run all day.", "Play with clean water for hours.", "Ignore a leaking tap."]),
            ("Which action is friendly to wild animals?", "Watch them from a safe distance.", ["Chase them for photos.", "Feed them unknown food.", "Throw stones at them."]),
            ("You see litter beside a river. What is a responsible choice?", "Pick it up safely and use a bin.", ["Kick it into the river.", "Hide it under a tree.", "Leave more litter there."]),
            ("Why should we keep forests clean?", "They are homes for many living things.", ["Because trees need homework.", "Because rivers go to school.", "Because mountains drink milk."]),
            ("Which sentence shows care for nature?", "We should leave flowers growing in the park.", ["We should pull up every flower.", "We should carve names into trees.", "We should throw cans on the path."]),
            ("A tap is dripping in the school washroom. What should you do?", "Close it and tell an adult if it still leaks.", ["Walk away and let it drip.", "Open it fully.", "Put paper in the sink."]),
            ("Which class rule best supports a clean environment?", "Reduce waste and sort rubbish.", ["Use more plastic for no reason.", "Drop paper on the floor.", "Leave lights on in empty rooms."]),
        ],
        explanation="根据生活情境判断保护环境、节约资源和尊重生物的合适行为。",
        seed_offset=2,
    )

    return rows


__all__ = ["ENGLISH_G5_TEXTBOOK", "grade5_english_specs"]
