import asyncio
import pygame
import random
import json
import os
import math
import traceback

GAME_W, GAME_H = 800, 450
BAG_START = 100
BAG10_COST = 500
BAG50_COST = 5000
START_MONEY = 5000
PRESTIGE_STEP = 10000
SAVE_FILE = "mining_save.json"
FONT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font.ttf")

pygame.init()

display_screen = pygame.display.set_mode((GAME_W, GAME_H))
screen = pygame.Surface((GAME_W, GAME_H))
clock = pygame.time.Clock()

WHITE = (245, 245, 245)
BLACK = (15, 18, 25)
BG = (18, 22, 32)
BLUE = (65, 100, 145)
DARK = (35, 40, 52)
PURPLE = (175, 90, 255)
GOLD = (255, 210, 70)
GRAY = (85, 115, 145)

FONT_CACHE = {}
TEXT_CACHE = {}

def get_font(size):
    if size not in FONT_CACHE:
        try:
            # 日本語対応フォント(同梱の font.ttf)を使う
            f = pygame.font.Font(FONT_FILE, size)
        except Exception:
            try:
                f = pygame.font.Font(None, size)
            except Exception:
                f = pygame.font.SysFont(None, size)
        FONT_CACHE[size] = f
    return FONT_CACHE[size]

def text_img(text, size, color):
    key = (text, size, color)
    img = TEXT_CACHE.get(key)
    if img is None:
        if len(TEXT_CACHE) > 600:
            TEXT_CACHE.clear()
        try:
            img = get_font(size).render(str(text), True, color)
        except Exception:
            img = get_font(size).render("?", True, color)
        TEXT_CACHE[key] = img
    return img

def present():
    display_screen.blit(screen, (0, 0))
    pygame.display.flip()

def convert_position(pos):
    return int(pos[0]), int(pos[1])

money = START_MONEY
bag = 0
bag_value = 0
bag_max = BAG_START
reset_confirm = 0
layer = 1
pickaxe = 1
robot_level = 0
prestige = 0
auto_sell = False
auto_pickaxe = False
auto_robot = False
player_x = 3
player_y = 0
world = []
robot_timer = 0
save_timer = 0
message = "矢印ボタンで移動しよう"
message_timer = 5
running = True
held_direction = None
held_timer = 0
REPEAT_DELAY = 0.12
REPEAT_INTERVAL = 0.075

def show_message(text, seconds=2):
    global message, message_timer
    message = str(text)
    message_timer = seconds

def all_dug():
    for row in world:
        for b in row:
            if not b["dug"]:
                return False
    return True

def block_base_value():
    cost = int(1000 * (1.35 ** min(layer - 1, 400)))
    return max(10, math.ceil(cost / 50))

def create_world():
    global world
    world = []
    for y in range(10):
        row = []
        for x in range(7):
            row.append({
                "dug": False,
                "required": layer,
                "value": block_base_value(),
                "gem": random.random() < min(0.35, 0.025 + layer * 0.0005 + prestige * 0.015),
            })
        world.append(row)

def save_game():
    data = {
        "money": money, "bag": bag, "bag_value": bag_value,
        "bag_max": bag_max, "layer": layer, "pickaxe": pickaxe,
        "robot_level": robot_level, "prestige": prestige,
        "auto_sell": auto_sell, "auto_pickaxe": auto_pickaxe,
        "auto_robot": auto_robot, "player_x": player_x,
        "player_y": player_y, "world": world,
    }
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def load_game():
    global money, bag, bag_value, bag_max
    global layer, pickaxe, robot_level, prestige
    global auto_sell, auto_pickaxe, auto_robot
    global player_x, player_y, world

    if not os.path.exists(SAVE_FILE):
        create_world()
        return
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        money = max(0, int(data.get("money", START_MONEY)))
        bag_max = max(BAG_START, int(data.get("bag_max", BAG_START)))
        bag = max(0, min(bag_max, int(data.get("bag", 0))))
        bag_value = max(0, int(data.get("bag_value", 0)))
        layer = max(1, min(500, int(data.get("layer", 1))))
        pickaxe = max(1, min(500, int(data.get("pickaxe", 1))))
        robot_level = max(0, min(500, int(data.get("robot_level", 0))))
        prestige = max(0, int(data.get("prestige", 0)))
        auto_sell = bool(data.get("auto_sell", False))
        auto_pickaxe = bool(data.get("auto_pickaxe", False))
        auto_robot = bool(data.get("auto_robot", False))
        player_x = max(0, min(6, int(data.get("player_x", 3))))
        player_y = max(0, min(9, int(data.get("player_y", 0))))
        saved = data.get("world", [])
        if isinstance(saved, list) and len(saved) == 10:
            world = saved
        else:
            create_world()
    except Exception:
        create_world()

def sell_bag():
    global bag, bag_value, money
    if bag <= 0:
        show_message("バッグは空です")
        return
    bonus = int(bag_value * 0.10)
    money += bonus
    bag = 0
    bag_value = 0
    show_message("売却ボーナス +" + format(bonus, ",") + " G")

def next_layer():
    global layer, player_x, player_y
    if layer >= 500:
        show_message("最深階層です")
        return
    required = layer + 1
    if pickaxe < required:
        show_message("次の階にはツルハシ Lv." + str(required) + " が必要です")
        return
    layer += 1
    player_x, player_y = 3, 0
    create_world()
    show_message("地下 " + str(layer) + " 階！")

def mine_block(x, y, by_robot=False):
    global money, bag, bag_value
    if not (0 <= x < 7 and 0 <= y < 10):
        return False
    block = world[y][x]
    if block["dug"]:
        return True
    if layer > pickaxe:
        if not by_robot:
            show_message("ツルハシ Lv." + str(layer) + " が必要です！")
        return False
    required = int(block.get("required", layer))
    if pickaxe < required:
        if not by_robot:
            show_message("採掘失敗！必要ツルハシ Lv." + str(required))
        return False

    if not by_robot and bag >= bag_max:
        if auto_sell:
            sell_bag()
        else:
            show_message("バッグがいっぱいです！")
            return False

    block["dug"] = True
    value = int(block["value"] * (1 + prestige * 0.25))
    if block["gem"]:
        value *= 5
        if not by_robot:
            show_message("宝石発見！ +" + format(value, ",") + " G")

    if by_robot:
        money += value + int(value * 0.10)
    else:
        money += value
        bag += 1
        bag_value += value
        if bag >= bag_max and auto_sell:
            sell_bag()

    if all_dug():
        if layer < 500:
            next_layer()
        else:
            show_message("500階到達！転生できます")
    return True

def move_player(dx, dy):
    global player_x, player_y
    nx = max(0, min(6, player_x + dx))
    ny = max(0, min(9, player_y + dy))
    if nx == player_x and ny == player_y:
        return
    if mine_block(nx, ny):
        player_x, player_y = nx, ny

def pickaxe_cost():
    return int(1000 * (1.35 ** min(pickaxe - 1, 400)))

def robot_cost():
    return math.ceil(37500 * (1.0001 ** max(0, robot_level - 1)))

def upgrade_pickaxe():
    global money, pickaxe
    if pickaxe >= 500:
        show_message("ツルハシ最大レベル")
        return
    cost = pickaxe_cost()
    if money < cost:
        show_message("お金が足りません")
        return
    money -= cost
    pickaxe += 1
    show_message("ツルハシ Lv." + str(pickaxe))
    if all_dug() and layer < pickaxe and layer < 500:
        next_layer()

def upgrade_robot():
    global money, robot_level
    if robot_level >= 500:
        show_message("ロボット最大レベル")
        return
    cost = robot_cost()
    if money >= cost:
        money -= cost
        robot_level += 1
        show_message("ロボット Lv." + str(robot_level))
    else:
        show_message("お金が足りません")

def toggle_sell():
    global auto_sell, money
    if auto_sell:
        auto_sell = False
        show_message("自動売却 OFF")
    elif money >= 100000:
        money -= 100000
        auto_sell = True
        show_message("自動売却 ON")
    else:
        show_message("100,000 G必要です")

def toggle_pickaxe():
    global auto_pickaxe
    auto_pickaxe = not auto_pickaxe
    show_message("自動ツルハシ " + ("ON" if auto_pickaxe else "OFF"))

def toggle_robot():
    global auto_robot
    auto_robot = not auto_robot
    show_message("自動ロボット " + ("ON" if auto_robot else "OFF"))

def upgrade_bag(n, cost):
    global money, bag_max
    if money < cost:
        show_message(format(cost, ",") + " G必要です")
        return
    money -= cost
    bag_max += n
    show_message("カバン容量 " + str(bag_max))

def reset_game():
    global money, bag, bag_value, bag_max, layer, pickaxe
    global robot_level, prestige, auto_sell, auto_pickaxe
    global auto_robot, player_x, player_y, reset_confirm, held_direction
    if reset_confirm <= 0:
        reset_confirm = 3
        show_message("もう一度押すと全データが消えます！", 3)
        return
    reset_confirm = 0
    money = START_MONEY
    bag = 0
    bag_value = 0
    bag_max = BAG_START
    layer = 1
    pickaxe = 1
    robot_level = 0
    prestige = 0
    auto_sell = False
    auto_pickaxe = False
    auto_robot = False
    player_x, player_y = 3, 0
    held_direction = None
    try:
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
    except Exception:
        pass
    create_world()
    show_message("リセットしました")

def do_prestige():
    global money, bag, bag_value, layer, pickaxe, robot_level, prestige
    global auto_sell, auto_pickaxe, auto_robot, player_x, player_y
    if layer != 500 or not all_dug():
        show_message("500階をすべて採掘してください")
        return
    prestige += 1
    money = START_MONEY + PRESTIGE_STEP * prestige
    bag = 0
    bag_value = 0
    layer = 1
    pickaxe = 1
    robot_level = 0
    auto_sell = False
    auto_pickaxe = False
    auto_robot = False
    player_x, player_y = 3, 0
    create_world()
    show_message("転生成功！ 第" + str(prestige) + "回")

def robot_interval():
    base = max(0.1, 5 - (robot_level // 10) * 0.1)
    return max(0.05, base / (1 + prestige * 0.10))

def robot_mine():
    if robot_level <= 0 or layer > pickaxe:
        return
    for y in range(10):
        for x in range(7):
            block = world[y][x]
            if not block["dug"] and block["required"] <= pickaxe:
                mine_block(x, y, True)
                return

BUTTONS = {
    "pickaxe": pygame.Rect(10, 305, 185, 44),
    "robot": pygame.Rect(205, 305, 185, 44),
    "sell": pygame.Rect(400, 305, 185, 44),
    "prestige": pygame.Rect(595, 305, 195, 44),
    "auto_sell": pygame.Rect(10, 353, 185, 44),
    "auto_pickaxe": pygame.Rect(205, 353, 185, 44),
    "auto_robot": pygame.Rect(400, 353, 185, 44),
    "save": pygame.Rect(595, 353, 195, 44),
    "bag10": pygame.Rect(10, 401, 185, 44),
    "bag50": pygame.Rect(205, 401, 185, 44),
    "reset": pygame.Rect(595, 401, 195, 44),
    "up": pygame.Rect(570, 130, 80, 58),
    "down": pygame.Rect(570, 230, 80, 58),
    "left": pygame.Rect(475, 180, 80, 58),
    "right": pygame.Rect(665, 180, 80, 58),
}

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

def draw_button(rect, text):
    pygame.draw.rect(screen, BLUE, rect)
    pygame.draw.rect(screen, WHITE, rect, 1)
    lines = text if isinstance(text, list) else [text]
    line_height = get_font(18).get_linesize()
    start_y = rect.centery - (line_height * len(lines)) // 2
    for i, line in enumerate(lines):
        img = text_img(line, 18, WHITE)
        screen.blit(img, (rect.centerx - img.get_width() // 2, start_y + i * line_height))

def handle_click(pos):
    global held_direction, held_timer
    for name, direction in DIRECTIONS.items():
        if BUTTONS[name].collidepoint(pos):
            move_player(*direction)
            held_direction = direction
            held_timer = 0
            return
    if BUTTONS["pickaxe"].collidepoint(pos): upgrade_pickaxe()
    elif BUTTONS["robot"].collidepoint(pos): upgrade_robot()
    elif BUTTONS["sell"].collidepoint(pos): sell_bag()
    elif BUTTONS["prestige"].collidepoint(pos): do_prestige()
    elif BUTTONS["auto_sell"].collidepoint(pos): toggle_sell()
    elif BUTTONS["auto_pickaxe"].collidepoint(pos): toggle_pickaxe()
    elif BUTTONS["auto_robot"].collidepoint(pos): toggle_robot()
    elif BUTTONS["bag10"].collidepoint(pos): upgrade_bag(10, BAG10_COST)
    elif BUTTONS["bag50"].collidepoint(pos): upgrade_bag(50, BAG50_COST)
    elif BUTTONS["reset"].collidepoint(pos): reset_game()
    elif BUTTONS["save"].collidepoint(pos): save_game(); show_message("セーブしました")

def release_direction():
    global held_direction, held_timer
    held_direction = None
    held_timer = 0

CELL = 22
GRID_X = 25
GRID_Y = 60

def draw():
    screen.fill(BG)
    screen.blit(text_img("地下採掘王", 27, GOLD), (12, 5))
    screen.blit(text_img(f"階層: {layer}", 15, WHITE), (240, 12))
    screen.blit(text_img(f"ツルハシ Lv.{pickaxe}", 15, WHITE), (330, 12))
    screen.blit(text_img(f"ロボット Lv.{robot_level}", 15, WHITE), (460, 12))
    screen.blit(text_img(f"所持金: {format(money, ',')} G", 15, GOLD), (590, 12))
    screen.blit(text_img(f"バッグ: {bag}/{bag_max}", 15, WHITE), (590, 35))
    screen.blit(text_img(f"転生: {prestige}", 15, WHITE), (460, 35))

    for y in range(10):
        for x in range(7):
            block = world[y][x]
            rect = pygame.Rect(GRID_X + x * CELL, GRID_Y + y * CELL, CELL - 2, CELL - 2)
            color = DARK if block["dug"] else (PURPLE if block["gem"] else GRAY)
            pygame.draw.rect(screen, color, rect)

    px = GRID_X + player_x * CELL + CELL // 2
    py = GRID_Y + player_y * CELL + CELL // 2
    pygame.draw.circle(screen, WHITE, (px, py), 8)

    if robot_level > 0:
        pygame.draw.circle(screen, BLACK, (GRID_X + 185, GRID_Y + 12), 8)

    draw_button(BUTTONS["up"], "↑")
    draw_button(BUTTONS["down"], "↓")
    draw_button(BUTTONS["left"], "←")
    draw_button(BUTTONS["right"], "→")

    pt = ["ツルハシ強化", "最大レベル"] if pickaxe >= 500 else ["ツルハシ強化", f"必要: {format(pickaxe_cost(), ',')} G"]
    rt = ["ロボット強化", "最大レベル"] if robot_level >= 500 else ["ロボット強化", f"必要: {format(robot_cost(), ',')} G"]

    draw_button(BUTTONS["pickaxe"], pt)
    draw_button(BUTTONS["robot"], rt)
    draw_button(BUTTONS["sell"], "売却")
    draw_button(BUTTONS["prestige"], "転生")
    draw_button(BUTTONS["auto_sell"], f"自動売却 {'ON' if auto_sell else 'OFF'}")
    draw_button(BUTTONS["auto_pickaxe"], f"自動ツルハシ {'ON' if auto_pickaxe else 'OFF'}")
    draw_button(BUTTONS["auto_robot"], f"自動ロボ {'ON' if auto_robot else 'OFF'}")
    draw_button(BUTTONS["save"], "セーブ")
    draw_button(BUTTONS["bag10"], ["カバン +10", f"{format(BAG10_COST, ',')} G"])
    draw_button(BUTTONS["bag50"], ["カバン +50", f"{format(BAG50_COST, ',')} G"])
    draw_button(BUTTONS["reset"], "全データリセット")

    screen.blit(text_img(message, 15, GOLD), (25, 283))
    present()

async def main():
    global running, robot_timer, save_timer, message_timer
    global money, pickaxe, robot_level, reset_confirm, held_direction, held_timer

    load_game()
    last_time = pygame.time.get_ticks()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP: move_player(0, -1)
                elif event.key == pygame.K_DOWN: move_player(0, 1)
                elif event.key == pygame.K_LEFT: move_player(-1, 0)
                elif event.key == pygame.K_RIGHT: move_player(1, 0)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                handle_click(convert_position(event.pos))

        now = pygame.time.get_ticks()
        dt = min((now - last_time) / 1000.0, 0.05)
        last_time = now

        if robot_level > 0:
            robot_timer += dt
            if robot_timer >= robot_interval():
                robot_timer = 0
                robot_mine()

        if reset_confirm > 0: reset_confirm -= dt
        if message_timer > 0: message_timer -= dt

        draw()
        clock.tick(30)
        await asyncio.sleep(0)

asyncio.run(main())
