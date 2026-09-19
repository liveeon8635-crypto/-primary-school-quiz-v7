"""Grade 5 English (PEP) baseline question pack.

The pack follows the skill domains of the current PEP Grade 5 upper-primary
course while using original stems and mini-passages. It avoids copied textbook
dialogues and audio-dependent questions so every item can be completed and
auto-graded in the existing web quiz flow.
"""

from __future__ import annotations

from typing import Any


ENGLISH_G5_TEXTBOOK = "人教PEP"


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
    for fallback in ("I don't know.", "None of them.", "Maybe.", "No."):
        if len(unique) >= 3:
            break
        if fallback != answer and fallback not in unique:
            unique.append(fallback)
    unique = unique[:3]
    correct_index = seed % 4
    options = list(unique)
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


def grade5_english_specs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # Unit 1 — describing people.
    traits = [
        ("kind", "友善的", ["严格的", "害羞的", "疲倦的"]),
        ("strict", "严格的", ["有趣的", "年轻的", "安静的"]),
        ("funny", "有趣的；滑稽的", ["勤奋的", "有礼貌的", "年老的"]),
        ("clever", "聪明的", ["强壮的", "缓慢的", "饥饿的"]),
        ("polite", "有礼貌的", ["口渴的", "吵闹的", "生气的"]),
        ("hard-working", "勤奋的", ["懒散的", "伤心的", "高大的"]),
        ("helpful", "乐于助人的", ["昂贵的", "危险的", "空的"]),
        ("shy", "害羞的", ["勇敢地大笑", "非常饥饿", "十分昂贵"]),
        ("young", "年轻的", ["古老的", "困难的", "甜的"]),
        ("quiet", "安静的", ["咸的", "繁忙的", "湿的"]),
    ]
    for i, (word, answer, distractors) in enumerate(traits):
        rows.append(_spec(
            unit="Unit 1 · What's he like?",
            knowledge="人物特征词汇",
            text=f'What does "{word}" mean in Chinese?',
            answer=answer,
            distractors=distractors,
            explanation="根据人物特征词汇的常用含义选择正确中文释义。",
            seed=i,
        ))

    descriptions = [
        ("Mr Li never gets angry and often helps us.", "He is kind.", ["He is thirsty.", "He is sweet.", "He is cloudy."]),
        ("Amy always says “please” and “thank you”.", "She is polite.", ["She is salty.", "She is rainy.", "She is old."]),
        ("Ben studies carefully every day.", "He is hard-working.", ["He is empty.", "He is sour.", "He is broken."]),
        ("Lily speaks very little when she meets new people.", "She is shy.", ["She is spicy.", "She is round.", "She is heavy."]),
        ("Our teacher makes us laugh in class.", "He is funny.", ["He is cold.", "He is dirty.", "He is square."]),
        ("Tom can solve difficult puzzles quickly.", "He is clever.", ["He is bitter.", "He is cloudy.", "He is thirsty."]),
        ("My grandpa is 70 years old.", "He is old.", ["He is young.", "He is sweet.", "He is loud."]),
        ("The new teacher is only 24.", "She is young.", ["She is old.", "She is sour.", "She is rainy."]),
        ("Our librarian speaks softly and the room is calm.", "She is quiet.", ["She is salty.", "She is hungry.", "She is windy."]),
        ("Ms Wang asks us to finish every task on time.", "She is strict.", ["She is sweet.", "She is cloudy.", "She is tiny."]),
    ]
    for i, (stem, answer, distractors) in enumerate(descriptions):
        rows.append(_spec(
            unit="Unit 1 · What's he like?",
            knowledge="人物描述句型",
            text=f"{stem} Which sentence describes the person best?",
            answer=answer,
            distractors=distractors,
            explanation="根据语境选择合适的人物特征，并使用 he/she + be + adjective。",
            seed=i + 1,
        ))

    # Unit 2 — week and routines.
    day_pairs = [
        ("The day after Monday is ____.", "Tuesday", ["Sunday", "Thursday", "Saturday"]),
        ("The day before Friday is ____.", "Thursday", ["Tuesday", "Saturday", "Monday"]),
        ("The day after Wednesday is ____.", "Thursday", ["Tuesday", "Friday", "Sunday"]),
        ("The day before Monday is ____.", "Sunday", ["Tuesday", "Friday", "Wednesday"]),
        ("The day after Friday is ____.", "Saturday", ["Monday", "Thursday", "Wednesday"]),
        ("The day before Sunday is ____.", "Saturday", ["Monday", "Tuesday", "Friday"]),
        ("There are seven days in a ____.", "week", ["month", "class", "room"]),
        ("Saturday and Sunday are the ____.", "weekend", ["weekday", "season", "lesson"]),
        ("Which word is a weekday?", "Wednesday", ["weekend", "today", "homework"]),
        ("Which pair is the weekend?", "Saturday and Sunday", ["Monday and Tuesday", "Wednesday and Thursday", "Thursday and Friday"]),
    ]
    for i, (text, answer, distractors) in enumerate(day_pairs):
        rows.append(_spec(
            unit="Unit 2 · My week",
            knowledge="星期与时间词汇",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="根据一周七天的顺序和 weekend/weekday 的含义作答。",
            seed=i + 2,
        ))

    schedules = [
        ("Monday: Chinese and maths; Tuesday: English and art. What do you have on Tuesday?", "English and art.", ["Chinese and maths.", "PE and music.", "Science and maths."]),
        ("Wednesday: PE; Thursday: music. When do you have PE?", "On Wednesday.", ["On Thursday.", "On Friday.", "On Sunday."]),
        ("I read books every Saturday. What do I do on Saturdays?", "You read books.", ["You play football.", "You wash clothes.", "You draw pictures."]),
        ("Mia often plays football on Sunday. What does Mia do on Sunday?", "She plays football.", ["She has maths.", "She cooks lunch.", "She sleeps at school."]),
        ("We have science on Friday. Which sentence is correct?", "We have science on Friday.", ["We has science on Friday.", "We have science in Friday.", "We having science Friday."]),
        ("What do you have on Mondays?", "I have Chinese and maths.", ["I am Chinese and maths.", "I has Chinese and maths.", "I have Monday."]),
        ("What do you do on the weekend?", "I often read books.", ["I often reads books.", "I am read books.", "I reading often books."]),
        ("Do you often play sports on Sundays?", "Yes, I do.", ["Yes, I am.", "Yes, I can do.", "Yes, I does."]),
        ("Does Jack often watch TV on Saturday?", "Yes, he does.", ["Yes, he do.", "Yes, he is.", "Yes, Jack do."]),
        ("Sara often ____ her homework after dinner.", "does", ["do", "doing", "is do"]),
    ]
    for i, (text, answer, distractors) in enumerate(schedules):
        rows.append(_spec(
            unit="Unit 2 · My week",
            knowledge="周计划与一般现在时",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="根据日程信息和一般现在时的人称变化选择正确表达。",
            seed=i + 3,
        ))

    # Unit 3 — food and preferences.
    foods = [
        ("Which word means “三明治”?", "sandwich", ["salad", "tea", "fresh"]),
        ("Which word means “沙拉”?", "salad", ["sandwich", "ice", "young"]),
        ("Which word means “汉堡包”?", "hamburger", ["river", "village", "bridge"]),
        ("Which word means “茶”?", "tea", ["tree", "eat", "day"]),
        ("Which word means “新鲜的”?", "fresh", ["strict", "behind", "funny"]),
        ("Which word means “健康的”?", "healthy", ["cloudy", "old", "under"]),
        ("Which word means “甜的”?", "sweet", ["quiet", "tall", "near"]),
        ("Which word means “辣的”?", "hot", ["soft", "young", "high"]),
        ("Which word is a drink?", "milk", ["bread", "salad", "rice"]),
        ("Which word is a food?", "noodles", ["water", "juice", "tea"]),
    ]
    for i, (text, answer, distractors) in enumerate(foods):
        rows.append(_spec(
            unit="Unit 3 · What would you like?",
            knowledge="食物与味觉词汇",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="辨认常见食物、饮料和描述食物的形容词。",
            seed=i,
        ))

    preferences = [
        ("—What would you like to eat? —____", "I'd like some noodles.", ["I can swim.", "It's Monday.", "There is a bed."]),
        ("—What would you like to drink? —____", "I'd like some water.", ["I'd like a book.", "I am strict.", "I play football."]),
        ("—What's your favourite food? —____", "Salad.", ["Tuesday.", "Near the lake.", "She is kind."]),
        ("—What's your favourite drink? —____", "Milk.", ["Rice.", "Friday.", "A bridge."]),
        ("I like vegetables. They are ____.", "healthy", ["behind", "strict", "shy"]),
        ("The cake has lots of sugar. It is very ____.", "sweet", ["quiet", "young", "helpful"]),
        ("Would you like some tea?", "Yes, please.", ["Yes, I can.", "Yes, there is.", "Yes, he does."]),
        ("I don't like very spicy food. The soup is too ____ for me.", "hot", ["polite", "clever", "near"]),
        ("Which sentence is correct?", "I'd like some rice.", ["I like would rice.", "I'd rice some like.", "I would some rice."]),
        ("Which question asks about a favourite food?", "What's your favourite food?", ["What can you do?", "What's he like?", "Is there a river?"]),
    ]
    for i, (text, answer, distractors) in enumerate(preferences):
        rows.append(_spec(
            unit="Unit 3 · What would you like?",
            knowledge="饮食偏好句型",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="使用 would like 和 favourite 的常用问答表达饮食偏好。",
            seed=i + 1,
        ))

    # Unit 4 — abilities.
    abilities = [
        ("Which phrase means “画漫画”?", "draw cartoons", ["play the pipa", "do homework", "read Monday"]),
        ("Which phrase means “唱英文歌”?", "sing English songs", ["speak river", "drink English", "cook Monday"]),
        ("Which phrase means “练武术”?", "do kung fu", ["do sandwich", "make river", "play strict"]),
        ("Which phrase means “弹琵琶”?", "play the pipa", ["draw the pipa", "read the pipa", "eat the pipa"]),
        ("Which phrase means “打篮球”?", "play basketball", ["do basketball", "play water", "make basketball"]),
        ("I can ____.", "swim", ["swims", "swimming", "to swimming"]),
        ("She can ____ English songs.", "sing", ["sings", "singing", "to sing"]),
        ("Can you cook?", "Yes, I can.", ["Yes, I do.", "Yes, I am.", "Yes, I have."]),
        ("Can Tom play basketball?", "No, he can't.", ["No, he doesn't can.", "No, he isn't.", "No, he don't."]),
        ("Which sentence is correct?", "We can dance.", ["We can dancing.", "We cans dance.", "We can to dance."]),
    ]
    for i, (text, answer, distractors) in enumerate(abilities):
        rows.append(_spec(
            unit="Unit 4 · What can you do?",
            knowledge="能力词汇与can",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="can 后接动词原形；一般疑问句用 Can ...? 回答用 can/can't。",
            seed=i + 2,
        ))

    ability_context = [
        ("Lucy can play the pipa, but she can't swim. What can Lucy do?", "She can play the pipa.", ["She can swim.", "She can fly.", "She can drive."]),
        ("Mike can cook and wash clothes. Which is true?", "Mike can cook.", ["Mike can't cook.", "Mike is a river.", "Mike has Monday."]),
        ("—What can you do for the party? —____", "I can sing.", ["I am Monday.", "There is a desk.", "I'd like water."]),
        ("We need someone to make pictures for the poster. Who can help?", "A student who can draw.", ["A student who can swim.", "A student who can cook rice.", "A student who can run fast."]),
        ("Ben cannot play ping-pong. Which sentence means the same?", "Ben can't play ping-pong.", ["Ben doesn't ping-pong.", "Ben isn't ping-pong.", "Ben can ping-pong."]),
        ("Can your sister dance?", "Yes, she can.", ["Yes, she does.", "Yes, she is.", "Yes, she has."]),
        ("What can the robot do? It can speak English. Which is correct?", "The robot can speak English.", ["The robot speaks can English.", "The robot can speaks English.", "The robot speaking English can."]),
        ("I can sing, and Amy can sing too. Which is true?", "Both of us can sing.", ["Neither of us can sing.", "Only Amy can sing.", "Only I can sing."]),
        ("Can he draw cartoons? He has never learned to draw.", "No, he can't.", ["Yes, he does.", "No, he isn't.", "Yes, he has."]),
        ("Which question asks about ability?", "What can you do?", ["What would you like?", "What's he like?", "What's in the room?"]),
    ]
    for i, (text, answer, distractors) in enumerate(ability_context):
        rows.append(_spec(
            unit="Unit 4 · What can you do?",
            knowledge="能力信息理解",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="从短句或情境中提取人物会做和不会做的事情。",
            seed=i + 3,
        ))

    # Unit 5 — room, there be, prepositions.
    room_words = [
        ("Which word means “时钟”?", "clock", ["lake", "forest", "salad"]),
        ("Which word means “植物”?", "plant", ["bridge", "week", "strict"]),
        ("Which word means “自行车”?", "bike", ["river", "tea", "polite"]),
        ("Which word means “照片”?", "photo", ["food", "village", "Monday"]),
        ("Which word means “瓶子”?", "bottle", ["mountain", "sandwich", "teacher"]),
        ("The book is ____ the desk. It is on the desk, not under it.", "on", ["under", "behind", "between"]),
        ("The cat is ____ the table. You cannot see it from the front.", "behind", ["on", "in", "above"]),
        ("The shoes are ____ the bed.", "under", ["on", "in front of", "between"]),
        ("The desk is ____ the bed and the window.", "between", ["under", "in", "above"]),
        ("The chair is ____ the desk, facing it.", "in front of", ["under", "inside", "between"]),
    ]
    for i, (text, answer, distractors) in enumerate(room_words):
        rows.append(_spec(
            unit="Unit 5 · There is a big bed",
            knowledge="房间物品与方位介词",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="掌握房间物品词汇和 on/under/behind/between/in front of 等方位介词。",
            seed=i,
        ))

    there_be = [
        ("____ a clock on the wall.", "There is", ["There are", "They are", "It have"]),
        ("____ two plants near the window.", "There are", ["There is", "It is", "There have"]),
        ("There ____ a desk and two chairs in the room.", "is", ["are", "be", "have"]),
        ("There ____ three books on the desk.", "are", ["is", "am", "has"]),
        ("Is there a computer in the room?", "Yes, there is.", ["Yes, there are.", "Yes, it does.", "Yes, it can."]),
        ("Are there any photos on the wall?", "No, there aren't.", ["No, there isn't.", "No, they don't.", "No, it can't."]),
        ("Which sentence is correct?", "There is a bike beside the door.", ["There are a bike beside the door.", "There is bike beside door.", "There have a bike."]),
        ("Which sentence is correct?", "There are some books on the shelf.", ["There is some books on the shelf.", "There are a books on the shelf.", "There have books on shelf."]),
        ("How many chairs are there? There are four chairs.", "Four.", ["One.", "Five.", "No chairs."]),
        ("There is no TV in my bedroom. Which is true?", "There isn't a TV in the bedroom.", ["There are two TVs.", "The TV is under the bed.", "The bedroom is a TV."]),
    ]
    for i, (text, answer, distractors) in enumerate(there_be):
        rows.append(_spec(
            unit="Unit 5 · There is a big bed",
            knowledge="There be句型",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="根据后面名词的单复数使用 there is / there are，并掌握一般疑问句。",
            seed=i + 1,
        ))

    # Unit 6 — nature.
    nature = [
        ("Which word means “森林”?", "forest", ["clock", "salad", "teacher"]),
        ("Which word means “河流”?", "river", ["photo", "week", "sandwich"]),
        ("Which word means “湖泊”?", "lake", ["plant", "strict", "Tuesday"]),
        ("Which word means “高山”?", "mountain", ["bottle", "tea", "polite"]),
        ("Which word means “村庄”?", "village", ["bedroom", "hamburger", "weekend"]),
        ("Which word means “桥”?", "bridge", ["salad", "young", "clock"]),
        ("There are many trees. It is a ____.", "forest", ["bridge", "bottle", "week"]),
        ("Water flows through the park in a long narrow way. It is a ____.", "river", ["mountain", "village", "clock"]),
        ("People can walk across the water on a ____.", "bridge", ["lake", "forest", "salad"]),
        ("A small group of houses in the countryside is a ____.", "village", ["river", "mountain", "bottle"]),
    ]
    for i, (text, answer, distractors) in enumerate(nature):
        rows.append(_spec(
            unit="Unit 6 · In a nature park",
            knowledge="自然景物词汇",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="辨认 nature park 场景中的常见自然景物词汇。",
            seed=i + 2,
        ))

    nature_questions = [
        ("Is there a river in the park? Yes, there is. Which is true?", "The park has a river.", ["The park has no river.", "There are two rivers for sure.", "The river is a classroom."]),
        ("Are there any mountains near the village? No, there aren't. Which is true?", "There are no mountains near the village.", ["There is one mountain.", "There are many mountains.", "The village is a mountain."]),
        ("There is a lake and there are two bridges. How many bridges are there?", "Two.", ["One.", "Three.", "No bridges."]),
        ("Which question is correct?", "Are there any trees?", ["Is there any trees?", "Are there a tree?", "There are any trees?"]),
        ("Which answer matches “Is there a lake?”", "Yes, there is.", ["Yes, there are.", "Yes, it do.", "Yes, I can."]),
        ("Which answer matches “Are there any houses?”", "Yes, there are.", ["Yes, there is.", "Yes, it has.", "Yes, I am."]),
        ("The park has one lake, two bridges and many trees. Which is NOT mentioned?", "A mountain.", ["A lake.", "Bridges.", "Trees."]),
        ("The village is beside the river. Where is the village?", "Beside the river.", ["Under the river.", "In the river.", "Above the sky."]),
        ("There are no tall buildings in the nature park. Which sentence means the same?", "There aren't any tall buildings.", ["There is a tall building.", "There are many tall buildings.", "The buildings can swim."]),
        ("Which sentence describes a nature park?", "There is a lake and many trees.", ["There is a bed and a clock.", "I have maths on Monday.", "I'd like some noodles."]),
    ]
    for i, (text, answer, distractors) in enumerate(nature_questions):
        rows.append(_spec(
            unit="Unit 6 · In a nature park",
            knowledge="自然公园问答",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="结合 there be 句型和自然景物信息完成问答与判断。",
            seed=i + 3,
        ))

    # Cross-unit grammar and reading.
    grammar = [
        ("Choose the correct sentence.", "She is helpful.", ["She are helpful.", "She helpful is.", "She be helpful."]),
        ("Choose the correct sentence.", "We have English on Tuesday.", ["We has English on Tuesday.", "We have English at Tuesday.", "We having English Tuesday."]),
        ("Choose the correct sentence.", "I'd like some tea.", ["I'd like tea some.", "I like would some tea.", "I would some tea like."]),
        ("Choose the correct sentence.", "He can swim.", ["He can swims.", "He cans swim.", "He can to swim."]),
        ("Choose the correct sentence.", "There is a photo on the wall.", ["There are a photo on the wall.", "There is photo on wall a.", "There have a photo."]),
        ("Choose the correct sentence.", "There are two bridges in the park.", ["There is two bridges in the park.", "There are two bridge in the park.", "There have two bridges."]),
        ("Which word completes the sentence? Amy ____ kind.", "is", ["are", "am", "be"]),
        ("Which word completes the sentence? We ____ PE on Friday.", "have", ["has", "is", "can has"]),
        ("Which word completes the sentence? Tom can ____ football.", "play", ["plays", "playing", "played"]),
        ("Which word completes the sentence? There ____ some trees near the lake.", "are", ["is", "am", "has"]),
    ]
    for i, (text, answer, distractors) in enumerate(grammar):
        rows.append(_spec(
            unit="Recycle · Language use",
            knowledge="核心语法综合",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="综合检查 be、一般现在时、would like、can 和 there be 等核心结构。",
            seed=i,
        ))

    readings = [
        ("Read: Leo is kind and funny. He often helps his classmates. What is Leo like?", "He is kind and funny.", ["He is strict and shy.", "He is a lake.", "He is Friday."]),
        ("Read: On Monday, Eva has Chinese, maths and PE. What does Eva have on Monday?", "Chinese, maths and PE.", ["English and art.", "Only music.", "No classes."]),
        ("Read: Sam likes vegetables and fish. His favourite drink is milk. What is Sam's favourite drink?", "Milk.", ["Fish.", "Vegetables.", "Tea."]),
        ("Read: Anna can dance and draw cartoons, but she can't swim. What can't Anna do?", "Swim.", ["Dance.", "Draw cartoons.", "Read."]),
        ("Read: My room has a bed, a desk and a plant. The plant is beside the desk. Where is the plant?", "Beside the desk.", ["Under the bed.", "In the lake.", "Behind a mountain."]),
        ("Read: There is a river in the park. There are three bridges over it. How many bridges are there?", "Three.", ["One.", "Two.", "Four."]),
        ("Read: Tina is hard-working. She does homework after school and reads books on Sunday. What does she do on Sunday?", "She reads books.", ["She swims.", "She cooks noodles.", "She goes to school."]),
        ("Read: Jack would like a sandwich and some water for lunch. What would Jack like to drink?", "Water.", ["A sandwich.", "Rice.", "Salad."]),
        ("Read: Ben can cook but cannot dance. What can Ben do?", "Cook.", ["Dance.", "Fly.", "Drive."]),
        ("Read: The village is near a forest. There is a small river and one bridge. What is near the village?", "A forest.", ["A classroom.", "A bedroom.", "A restaurant."]),
    ]
    for i, (text, answer, distractors) in enumerate(readings):
        rows.append(_spec(
            unit="Recycle · Reading",
            knowledge="短文信息提取",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="从简短原创英语材料中定位人物、时间、喜好、能力、方位和数量等明确事实。",
            seed=i + 1,
        ))

    return rows


__all__ = ["ENGLISH_G5_TEXTBOOK", "grade5_english_specs"]
