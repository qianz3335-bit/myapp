import json
import os
import random
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Hello, Railway! My game is working."
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

SAVE_DIR = "saves"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

EVENTS = {
    "port": [
        {"name": "神秘商人", "desc": "一个戴着兜帽的商人悄悄拉住你，展示了几件奇异货物。"},
        {"name": "醉汉闹事", "desc": "酒馆外传来打斗声，一个醉醺醺的水手正被治安官拖走。"},
        {"name": "征兵令", "desc": "码头贴出国王的征兵令，皇家海军正在招募有经验的水手。"},
        {"name": "走私者接头", "desc": "夜色中，几个人影在货栈旁窃窃私语，似乎在交易违禁品。"},
    ],
    "sea": [
        {"name": "暴风雨", "desc": "天空骤然变暗，狂风裹挟巨浪拍打着船舷。"},
        {"name": "海盗船", "desc": "一面黑色的骷髅旗出现在海平线上，对方正在加速靠近。"},
        {"name": "鲸群", "desc": "一群座头鲸跃出海面，壮观的水花喷向天空。"},
        {"name": "漂流船", "desc": "一艘没有船员的破旧帆船在浪中起伏，船舱似乎有货。"},
        {"name": "海市蜃楼", "desc": "远方出现虚幻的岛屿景象，水手们议论纷纷。"},
    ]
}

# ==================== 系统提示词 ====================
SYSTEM_PROMPT = """
你是文字游戏《诸海风云》的剧情主持人。你负责叙述世界,扮演所有非玩家角色,裁定玩家行为后果。

你严格遵循以下规则:
- 不存在神明,超自然,预定命运。
- 科技上限为17-18世纪,火器只能是滑膛前装枪炮,风帆主导航海。
- 永远不为玩家降低难度,每次胜利必有代价。
- 叙事长度300-800字,纯描写与对话,不得出现括号。
- 每幕结束后必须输出以下格式的状态表格(用三个反引号包裹,无语言标记):
◆ 势力关系
- [人物/势力]对你态度:数值/100,原因
◆ 当前位置
- 地点:...
- 所属势力范围:...
- 周边地标:...
- 距主要城市:...
◆ 当前处境
- 身份状态:...
- 秘密行动:...
- ⚠️ 异常标记:...
◆ 资源
- 情报:...
- 盟友:...
- 物资/银两:...
- 其他:...
◆ 待命危机
- 危机名:触发条件[已满足/未满足],预计触发时间
◆ 世界变量
- 季节/时间:...
- 天气:...
- 其他变量...

然后输出世界状态日志,格式:
```log
- [时间推进]:...
- [关键事件]:...
- [新增情报]:...
- [角色变化]:...
- [伏笔埋设]:...
- [当前幕数]:第X幕
```

绝对禁止:
- 在末尾列出A/B/C选项或说"你可以..."。
- 使用括号描述动作。
- 出现现代词汇(自由,平等,人权等)。

主角设定:你叫伊恩,穿越者,目前在海风镇。初始状态如下:
◆ 势力关系
- 海风镇居民对你接纳度:40/100,外乡人但规矩本分
- 当地治安官关注度:5/100,暂无异常
◆ 当前位置
- 地点:海风镇
- 所属势力范围:安布利亚王国
- 周边地标:防波堤灯塔,圣玛利亚教堂,皇家马斯顿公司分行
- 距主要城市:金斯顿以北约200里
◆ 当前处境
- 身份状态:暂时无特殊身份
- 秘密行动:无
- ⚠️ 异常标记:无
◆ 资源
- 情报:海风镇日常见闻
- 盟友:老渔民马科(信任度70/100)
- 物资/银两:17枚安布利亚银先令
- 其他:一本汉字笔记(核心秘密)
◆ 待命危机
- 无
◆ 世界变量
- 季节/时间:初夏,午后
- 天气:晴朗
- 海风镇繁荣度:中等偏上
- 国际紧张度:缓慢上升

现在,玩家开始了游戏。请根据玩家输入生成第一幕叙事,然后输出状态表格和日志。不要列出任何选项。
"""

# ==================== 时间与天气管理 ====================
def init_game_time():
    return {
        "season": "初夏",
        "day": 1,
        "hour": 14,
        "weather": "晴朗"
    }

def advance_time(current_time, hours=6):
    new_hour = current_time["hour"] + hours
    day_inc = new_hour // 24
    new_hour = new_hour % 24
    new_day = current_time["day"] + day_inc
    seasons = ["初春", "暮春", "初夏", "盛夏", "初秋", "深秋", "初冬", "隆冬"]
    season_index = (new_day // 30) % len(seasons)
    new_season = seasons[season_index]
    weathers = ["晴朗", "多云", "阴雨", "风暴"]
    if current_time["weather"] == "风暴":
        weather = random.choices(weathers, weights=[70,20,10,0])[0]
    else:
        weather = random.choices(weathers, weights=[40,30,20,10])[0]
    return {
        "season": new_season,
        "day": new_day,
        "hour": new_hour,
        "weather": weather
    }

def get_weather_icon(weather):
    icons = {"晴朗":"☀️", "多云":"⛅", "阴雨":"🌧️", "风暴":"🌊"}
    return icons.get(weather, "☀️")

# ==================== 随机事件触发 ====================
def trigger_random_event(current_location, game_time):
    if "海风镇" in current_location or "港口" in current_location or "码头" in current_location:
        if random.random() < 0.2:
            event = random.choice(EVENTS["port"])
            return f"\n[随机事件] {event['name']}：{event['desc']}\n"
    elif "海" in current_location or "航行" in current_location or "船" in current_location:
        if random.random() < 0.3:
            event = random.choice(EVENTS["sea"])
            return f"\n[随机事件] {event['name']}：{event['desc']}\n"
    if game_time["hour"] < 5 or game_time["hour"] > 21:
        if random.random() < 0.15 and "海" in current_location:
            return f"\n[随机事件] 夜袭海盗：黑暗中几艘小艇悄悄靠近，您听到了钩爪搭上船舷的声音。\n"
    return ""

# ==================== 玩家状态 ====================
def init_player_status():
    return {"fatigue": 20, "health": 90}

def update_fatigue_on_action(current_status, hours_passed, action_type="normal"):
    fatigue = current_status["fatigue"]
    if action_type == "sleep":
        fatigue = max(0, fatigue - 30)
    elif action_type == "sail":
        fatigue += 8
    elif action_type == "night":
        fatigue += 5
    else:
        fatigue += 2
    fatigue = min(100, fatigue)
    health = current_status["health"]
    if fatigue > 80:
        health -= 5
    elif fatigue < 20:
        health = min(100, health + 2)
    health = max(0, min(100, health))
    return {"fatigue": fatigue, "health": health}

# ==================== 载具系统 ====================
def init_vessel():
    return {
        "name": "海鸥号",
        "type": "渔船",
        "speed": 5,        # 基础速度 1-10
        "cargo": 50,       # 容量单位
        "hull": 100,       # 耐久度
        "cannons": 2,      # 火炮数量
        "upgrades": {
            "speed_level": 0,
            "cargo_level": 0,
            "hull_level": 0,
            "cannons_level": 0
        }
    }

def upgrade_vessel(vessel, upgrade_type, current_silver):
    """尝试升级，返回 (new_vessel, cost, success, new_silver)"""
    upgrade_map = {
        "speed": {"level_key": "speed_level", "attr": "speed", "base_inc": 1, "max_level": 5, "cost_per_level": 50},
        "cargo": {"level_key": "cargo_level", "attr": "cargo", "base_inc": 20, "max_level": 5, "cost_per_level": 50},
        "hull": {"level_key": "hull_level", "attr": "hull", "base_inc": 30, "max_level": 5, "cost_per_level": 50},
        "cannons": {"level_key": "cannons_level", "attr": "cannons", "base_inc": 2, "max_level": 5, "cost_per_level": 50}
    }
    if upgrade_type not in upgrade_map:
        return vessel, 0, False, current_silver
    info = upgrade_map[upgrade_type]
    current_level = vessel["upgrades"][info["level_key"]]
    if current_level >= info["max_level"]:
        return vessel, 0, False, current_silver
    cost = info["cost_per_level"] * (current_level + 1)  # 累进价格，第一级50，第二级100... 也可固定每级50
    # 改为固定每级50银两
    cost = 50
    if current_silver < cost:
        return vessel, cost, False, current_silver
    # 执行升级
    vessel["upgrades"][info["level_key"]] += 1
    vessel[info["attr"]] += info["base_inc"]
    return vessel, cost, True, current_silver - cost

# ==================== 声望系统 ====================
def init_reputation():
    return {
        "安布利亚王国": 0,
        "加利斯王国": 0,
        "海盗兄弟会": -10,
        "教会": 0,
        "海风镇": 20
    }

def parse_reputation_from_text(text, current_rep):
    new_rep = current_rep.copy()
    mapping = {
        "安布利亚": "安布利亚王国",
        "加利斯": "加利斯王国",
        "海盗": "海盗兄弟会",
        "教会": "教会",
        "海风镇": "海风镇"
    }
    for keyword, faction in mapping.items():
        if re.search(rf'{keyword}.*(感谢|赞赏|帮助|支持|信任|友好)', text):
            new_rep[faction] = min(100, new_rep[faction] + random.randint(5, 15))
        if re.search(rf'{keyword}.*(敌视|仇恨|厌恶|攻击|背叛|怀疑)', text):
            new_rep[faction] = max(-100, new_rep[faction] - random.randint(5, 20))
        if re.search(rf'{keyword}.*(拯救|重大贡献|结盟)', text):
            new_rep[faction] = min(100, new_rep[faction] + 30)
        if re.search(rf'{keyword}.*(背叛|屠杀|劫掠)', text):
            new_rep[faction] = max(-100, new_rep[faction] - 40)
    return new_rep

# ==================== 成就系统 ====================
ACHIEVEMENTS = [
    {"id": "first_voyage", "name": "初航", "desc": "第一次出海", "condition": lambda state: state.get("first_sail", False)},
    {"id": "rich_100", "name": "小有积蓄", "desc": "银两达到100", "condition": lambda state: state.get("silver", 0) >= 100},
    {"id": "rich_1000", "name": "富甲一方", "desc": "银两达到1000", "condition": lambda state: state.get("silver", 0) >= 1000},
    {"id": "ally_high", "name": "挚友", "desc": "任意盟友信任度≥90", "condition": lambda state: any(trust >= 90 for trust in state.get("ally_trusts", []) if trust)},
    {"id": "pirate_hunter", "name": "海盗克星", "desc": "击败3次海盗", "condition": lambda state: state.get("pirate_defeats", 0) >= 3},
    {"id": "explorer", "name": "探险家", "desc": "访问5个不同地点", "condition": lambda state: len(state.get("visited_locations", [])) >= 5},
    {"id": "fatigue_crisis", "name": "濒临崩溃", "desc": "疲劳值达到100", "condition": lambda state: state.get("fatigue", 0) >= 100},
    {"id": "health_recovery", "name": "顽强", "desc": "健康从低于20恢复到80以上", "condition": lambda state: state.get("health_recovered", False)},
    {"id": "vessel_upgrade", "name": "船匠", "desc": "任意船只属性升级5次", "condition": lambda state: state.get("total_upgrades", 0) >= 5}
]

def check_achievements(session_data, new_state):
    unlocked = []
    for ach in ACHIEVEMENTS:
        if ach["id"] not in session_data["achievements_unlocked"]:
            if ach["condition"](new_state):
                unlocked.append(ach)
                session_data["achievements_unlocked"].append(ach["id"])
    return unlocked

# ==================== 自动摘要/日志 ====================
def add_log_entry(session_data, event_summary):
    session_data["log_entries"].append({
        "act": session_data["act"],
        "summary": event_summary,
        "time": session_data["game_time"].copy()
    })
    if len(session_data["log_entries"]) > 50:
        session_data["log_entries"] = session_data["log_entries"][-50:]

# ==================== 任务解析 ====================
def parse_tasks_from_text(text, existing_tasks):
    patterns = [
        r'委托[：:]\s*([^。\n]+)',
        r'任务[：:]\s*([^。\n]+)',
        r'接到了[一|个]*(?:个)?委托[：:]*\s*([^。\n]+)',
        r'有人托你办件事[：:]*\s*([^。\n]+)',
        r'“([^”]+委托[^”]+)”',
    ]
    new_tasks = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            task_name = m.strip()
            if len(task_name) > 5 and not any(t['name'] == task_name for t in existing_tasks):
                new_tasks.append({"name": task_name, "completed": False})
    seen = set()
    unique = []
    for t in new_tasks:
        if t['name'] not in seen:
            seen.add(t['name'])
            unique.append(t)
    return unique

def parse_player_status_from_text(text, current_status):
    fatigue_delta = 0
    health_delta = 0
    text_lower = text.lower()
    if re.search(r'疲惫|劳累|困倦|熬夜|连续工作|体力不支', text_lower):
        fatigue_delta += 10
    if re.search(r'精疲力尽|虚脱|累倒', text_lower):
        fatigue_delta += 15
    if re.search(r'休息|小憩|打了个盹|恢复体力', text_lower):
        fatigue_delta -= 15
    if re.search(r'睡了一觉|酣睡|睡得香甜|精神焕发', text_lower):
        fatigue_delta -= 30
    if re.search(r'恢复健康|伤口愈合|气色好转|身体好转', text_lower):
        health_delta += 10
    if re.search(r'彻底康复|痊愈', text_lower):
        health_delta += 20
    if re.search(r'受伤|伤口|流血|负伤', text_lower):
        health_delta -= 15
    if re.search(r'生病|发烧|感染|痢疾|坏血', text_lower):
        health_delta -= 20
    if re.search(r'重伤|濒死', text_lower):
        health_delta -= 40
    new_fatigue = max(0, min(100, current_status['fatigue'] + fatigue_delta))
    new_health = max(0, min(100, current_status['health'] + health_delta))
    return new_fatigue, new_health

# ==================== 会话管理 ====================
sessions = {}

def save_session_to_file(session_id):
    if session_id not in sessions:
        return False
    data = {
        "history": sessions[session_id]["history"],
        "act": sessions[session_id]["act"],
        "game_time": sessions[session_id]["game_time"],
        "tasks": sessions[session_id]["tasks"],
        "player_status": sessions[session_id]["player_status"],
        "reputation": sessions[session_id]["reputation"],
        "achievements_unlocked": sessions[session_id]["achievements_unlocked"],
        "log_entries": sessions[session_id]["log_entries"],
        "achievement_state": sessions[session_id]["achievement_state"],
        "vessel": sessions[session_id]["vessel"]
    }
    filepath = os.path.join(SAVE_DIR, f"{session_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True

def load_session_from_file(session_id):
    filepath = os.path.join(SAVE_DIR, f"{session_id}.json")
    if not os.path.exists(filepath):
        return False
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    sessions[session_id] = {
        "history": data["history"],
        "act": data["act"],
        "game_time": data.get("game_time", init_game_time()),
        "tasks": data.get("tasks", []),
        "player_status": data.get("player_status", init_player_status()),
        "reputation": data.get("reputation", init_reputation()),
        "achievements_unlocked": data.get("achievements_unlocked", []),
        "log_entries": data.get("log_entries", []),
        "achievement_state": data.get("achievement_state", {
            "first_sail": False,
            "silver": 17,
            "ally_trusts": [70],
            "pirate_defeats": 0,
            "visited_locations": ["海风镇"],
            "fatigue": 20,
            "health_recovered": False,
            "total_upgrades": 0
        }),
        "vessel": data.get("vessel", init_vessel())
    }
    return True

# ==================== API 路由 ====================
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400

    if session_id not in sessions:
        if not load_session_from_file(session_id):
            sessions[session_id] = {
                'history': [],
                'act': 1,
                'game_time': init_game_time(),
                'tasks': [],
                'player_status': init_player_status(),
                'reputation': init_reputation(),
                'achievements_unlocked': [],
                'log_entries': [],
                'achievement_state': {
                    "first_sail": False,
                    "silver": 17,
                    "ally_trusts": [70],
                    "pirate_defeats": 0,
                    "visited_locations": ["海风镇"],
                    "fatigue": 20,
                    "health_recovered": False,
                    "total_upgrades": 0
                },
                'vessel': init_vessel()
            }

    sess = sessions[session_id]
    history = sess['history']
    current_act = sess['act']
    game_time = sess['game_time']
    player_status = sess['player_status']
    rep = sess['reputation']
    ach_state = sess['achievement_state']
    vessel = sess['vessel']

    # 时间推进
    time_delta = 6
    action_type = "normal"
    if "出海" in user_message or "航行" in user_message:
        time_delta = 24
        action_type = "sail"
        ach_state["first_sail"] = True
    elif "睡觉" in user_message or "过夜" in user_message or "休息" in user_message:
        time_delta = 12
        action_type = "sleep"
    elif "熬夜" in user_message:
        time_delta = 8
        action_type = "night"
    new_time = advance_time(game_time, time_delta)
    sess['game_time'] = new_time

    # 更新疲劳/健康
    new_status = update_fatigue_on_action(player_status, time_delta, action_type)
    sess['player_status'] = new_status
    ach_state["fatigue"] = new_status["fatigue"]
    if player_status["health"] < 20 and new_status["health"] >= 80:
        ach_state["health_recovered"] = True

    # 提取当前地点
    current_location = "海风镇"
    for msg in reversed(history):
        if msg['role'] == 'assistant':
            loc_match = re.search(r'地点[：:]\s*([^\n]+)', msg['content'])
            if loc_match:
                current_location = loc_match.group(1).strip()
                if current_location not in ach_state["visited_locations"]:
                    ach_state["visited_locations"].append(current_location)
            break

    # 随机事件
    event_text = trigger_random_event(current_location, new_time)

    # 构建系统消息
    weather_icon = get_weather_icon(new_time['weather'])
    time_context = f"\n【当前时间】{new_time['season']}，第{new_time['day']}天，{new_time['hour']}:00。天气：{weather_icon} {new_time['weather']}。"
    if event_text:
        time_context += f"\n【突发事件】{event_text}"

    system_with_context = SYSTEM_PROMPT + time_context

    messages = [
        {"role": "system", "content": system_with_context},
        *history,
        {"role": "user", "content": user_message}
    ]

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.75,
        "max_tokens": 1200
    }

    try:
        response = requests.post(DEEPSEEK_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        reply = result['choices'][0]['message']['content']

        # 解析任务
        existing_tasks = sess['tasks']
        new_tasks = parse_tasks_from_text(reply, existing_tasks)
        if new_tasks:
            sess['tasks'].extend(new_tasks)

        # 解析身体状态
        new_fatigue, new_health = parse_player_status_from_text(reply, sess['player_status'])
        sess['player_status']['fatigue'] = new_fatigue
        sess['player_status']['health'] = new_health
        ach_state["fatigue"] = new_fatigue

        # 解析声望
        new_rep = parse_reputation_from_text(reply, rep)
        sess['reputation'] = new_rep

        # 从回复中提取银两变化
        silver_match = re.search(r'银两[：:]\s*(\d+)', reply)
        if silver_match:
            ach_state["silver"] = int(silver_match.group(1))

        # 提取盟友信任度
        trust_matches = re.findall(r'信任度(\d+)\/100', reply)
        if trust_matches:
            ach_state["ally_trusts"] = [int(t) for t in trust_matches]

        # 检测海盗击败
        if re.search(r'击败海盗|击沉海盗船|消灭海盗', reply):
            ach_state["pirate_defeats"] = ach_state.get("pirate_defeats", 0) + 1

        # 检测成就
        new_achievements = check_achievements(sess, ach_state)
        for ach in new_achievements:
            reply += f"\n\n✨ 成就解锁：{ach['name']} - {ach['desc']} ✨"

        # 添加日志条目
        summary = reply.split('\n')[0][:80] if reply else "剧情推进"
        add_log_entry(sess, summary)

        # 保存历史
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": reply})
        if len(history) > 20:
            sess['history'] = history[-20:]

        sess['act'] = current_act + 1
        save_session_to_file(session_id)

        # 获取银两数值（用于前端显示）
        current_silver = ach_state.get("silver", 17)

        return jsonify({
            'reply': reply,
            'act': current_act,
            'time': new_time,
            'event': event_text.strip(),
            'tasks': sess['tasks'],
            'player_status': sess['player_status'],
            'reputation': sess['reputation'],
            'new_achievements': [ach['name'] for ach in new_achievements],
            'log_entries': sess['log_entries'][-10:],
            'vessel': vessel,
            'silver': current_silver
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    sessions[session_id] = {
        'history': [],
        'act': 1,
        'game_time': init_game_time(),
        'tasks': [],
        'player_status': init_player_status(),
        'reputation': init_reputation(),
        'achievements_unlocked': [],
        'log_entries': [],
        'achievement_state': {
            "first_sail": False,
            "silver": 17,
            "ally_trusts": [70],
            "pirate_defeats": 0,
            "visited_locations": ["海风镇"],
            "fatigue": 20,
            "health_recovered": False,
            "total_upgrades": 0
        },
        'vessel': init_vessel()
    }
    filepath = os.path.join(SAVE_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({'status': 'ok', 'act': 1})

@app.route('/save', methods=['POST'])
def save():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    if save_session_to_file(session_id):
        return jsonify({'status': 'ok', 'message': '存档成功'})
    else:
        return jsonify({'error': '保存失败'}), 500

@app.route('/load', methods=['POST'])
def load():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    if load_session_from_file(session_id):
        act = sessions[session_id]['act']
        history = sessions[session_id]['history']
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history[-20:]]
        game_time = sessions[session_id].get('game_time', init_game_time())
        tasks = sessions[session_id].get('tasks', [])
        player_status = sessions[session_id].get('player_status', init_player_status())
        reputation = sessions[session_id].get('reputation', init_reputation())
        achievements = sessions[session_id].get('achievements_unlocked', [])
        log_entries = sessions[session_id].get('log_entries', [])
        vessel = sessions[session_id].get('vessel', init_vessel())
        silver = sessions[session_id]['achievement_state'].get('silver', 17)
        return jsonify({'status': 'ok', 'act': act, 'history': messages, 'time': game_time,
                        'tasks': tasks, 'player_status': player_status, 'reputation': reputation,
                        'achievements': achievements, 'log_entries': log_entries[-20:],
                        'vessel': vessel, 'silver': silver})
    else:
        return jsonify({'error': '没有找到存档'}), 404

@app.route('/rest', methods=['POST'])
def rest():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    old_time = sessions[session_id]['game_time']
    new_time = advance_time(old_time, 8)
    sessions[session_id]['game_time'] = new_time
    old_status = sessions[session_id]['player_status']
    new_fatigue = max(0, old_status['fatigue'] - 30)
    new_health = min(100, old_status['health'] + 2) if new_fatigue < 20 else old_status['health']
    new_status = {'fatigue': new_fatigue, 'health': new_health}
    sessions[session_id]['player_status'] = new_status
    save_session_to_file(session_id)
    return jsonify({'status': 'ok', 'time': new_time, 'player_status': new_status})

@app.route('/upgrade_vessel', methods=['POST'])
def upgrade_vessel():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    upgrade_type = data.get('type', '')  # speed, cargo, hull, cannons
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    sess = sessions[session_id]
    vessel = sess['vessel']
    current_silver = sess['achievement_state'].get('silver', 17)
    new_vessel, cost, success, new_silver = upgrade_vessel(vessel, upgrade_type, current_silver)
    if not success:
        return jsonify({'error': f'升级失败，需要{cost}银两或已达上限', 'success': False}), 400
    sess['vessel'] = new_vessel
    sess['achievement_state']['silver'] = new_silver
    # 增加总升级次数计数
    sess['achievement_state']['total_upgrades'] = sess['achievement_state'].get('total_upgrades', 0) + 1
    # 检测成就（可能触发“船匠”）
    new_achievements = check_achievements(sess, sess['achievement_state'])
    for ach in new_achievements:
        # 可额外通知前端，但简单起见，记录即可
        pass
    save_session_to_file(session_id)
    return jsonify({
        'success': True,
        'vessel': new_vessel,
        'silver': new_silver,
        'new_achievements': [ach['name'] for ach in new_achievements]
    })

@app.route('/get_achievements', methods=['GET'])
def get_achievements():
    session_id = request.args.get('session_id', 'default')
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    unlocked = sessions[session_id].get('achievements_unlocked', [])
    all_achievements = [{"id": a["id"], "name": a["name"], "desc": a["desc"], "unlocked": a["id"] in unlocked} for a in ACHIEVEMENTS]
    return jsonify(all_achievements)

@app.route('/get_logs', methods=['GET'])
def get_logs():
    session_id = request.args.get('session_id', 'default')
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    logs = sessions[session_id].get('log_entries', [])
    return jsonify(logs)

@app.route('/get_reputation', methods=['GET'])
def get_reputation():
    session_id = request.args.get('session_id', 'default')
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    rep = sessions[session_id].get('reputation', init_reputation())
    return jsonify(rep)

@app.route('/complete_task', methods=['POST'])
def complete_task():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    task_index = data.get('task_index', -1)
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    tasks = sessions[session_id]['tasks']
    if 0 <= task_index < len(tasks):
        tasks[task_index]['completed'] = True
        save_session_to_file(session_id)
        return jsonify({'status': 'ok', 'tasks': tasks})
    else:
        return jsonify({'error': '无效的任务索引'}), 400

@app.route('/add_task', methods=['POST'])
def add_task():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    task_name = data.get('task_name', '').strip()
    if not task_name:
        return jsonify({'error': '任务内容不能为空'}), 400
    if session_id not in sessions:
        return jsonify({'error': '会话不存在'}), 404
    sessions[session_id]['tasks'].append({"name": task_name, "completed": False})
    save_session_to_file(session_id)
    return jsonify({'status': 'ok', 'tasks': sessions[session_id]['tasks']})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
