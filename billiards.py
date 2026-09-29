import sys
import json
import os
import time
import pygame

pygame.init()

WIDTH, HEIGHT = 960, 500
TABLE_WIDTH = 820
TABLE_HEIGHT = 500
SIDE_PANEL_WIDTH = WIDTH - TABLE_WIDTH
BALL_RADIUS = 15
BALL_DIAMETER = BALL_RADIUS * 2
POCKET_RADIUS = 28
BOARD_WIDTH = 20
INDENT = 20
MAX_SHOT_POWER = 15.0
SETTINGS_FILE = "settingbiliard.json"

display = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Бильярд")
clock = pygame.time.Clock()

bg = (34, 139, 34)
ball_font = pygame.font.SysFont("Arial", 14, bold=True)
btn_font = pygame.font.Font(None, 42)
small_font = pygame.font.SysFont("Arial", 16)
score_font = pygame.font.SysFont("Arial", 18, bold=True)
title_font = pygame.font.SysFont("Impact", 56)

play_btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT // 2 - 30, 260, 55)
stats_btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT // 2 + 40, 260, 55)
exit_btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT // 2 + 110, 260, 55)
back_btn = pygame.Rect(WIDTH // 2 - 110, HEIGHT - 80, 220, 50)

game_status_rect = pygame.Rect(TABLE_WIDTH, 0, SIDE_PANEL_WIDTH, HEIGHT)

pockets = [
    pygame.math.Vector2(INDENT, INDENT),
    pygame.math.Vector2(INDENT, TABLE_HEIGHT - INDENT),
    pygame.math.Vector2(TABLE_WIDTH - INDENT, INDENT),
    pygame.math.Vector2(TABLE_WIDTH - INDENT, TABLE_HEIGHT - INDENT),
    pygame.math.Vector2(TABLE_WIDTH // 2 - BALL_RADIUS, INDENT),
    pygame.math.Vector2(TABLE_WIDTH // 2 - BALL_RADIUS, TABLE_HEIGHT - INDENT),
]

ball_numbers_by_color = {
    (184, 134, 11): 1,
    (25, 25, 112): 2,
    (139, 0, 0): 3,
    (75, 0, 130): 4,
    (211, 47, 0): 5,
    (0, 100, 0): 6,
    (101, 67, 33): 7,
    (20, 20, 20): 8,
    (184, 134, 12): 9,
    (25, 25, 113): 10,
    (139, 0, 1): 11,
    (75, 0, 131): 12,
    (211, 47, 1): 13,
    (0, 100, 1): 14,
    (101, 67, 34): 15,
}

pocket_sound = pygame.mixer.Sound('sound1.mp3')
cue_stroke_sound = pygame.mixer.Sound('sound2.mp3')
cue_stroke_ball_sound = pygame.mixer.Sound('sound3.mp3')
cue_ball_and_ball_sound = pygame.mixer.Sound('sound4.mp3')
cue_board_sound = pygame.mixer.Sound('sound5.mp3')


def default_stats():
    return {
        "games_played": 0,
        "balls_potted": 0,
        "wins": 0,
        "losses": 0,
        "best_time": None,
        "worst_time": None,
        "last_time": None,
    }


def load_stats():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError
            base = default_stats()
            for key, val in base.items():
                data.setdefault(key, val)
            return data
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    return default_stats()


def save_stats(stats):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def format_time(seconds):
    if seconds is None:
        return "—"
    seconds = float(seconds)
    minutes = int(seconds // 60)
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:05.2f}"


def winrate(stats):
    total = stats["wins"] + stats["losses"]
    if total == 0:
        return "—"
    return f"{stats['wins'] / total * 100:.1f}%"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


stats = load_stats()


class GameState:
    def __init__(self):
        self.ball_pos = pygame.math.Vector2(500, 250)
        self.ball_vel = pygame.math.Vector2(0, 0)
        self.balls_positions = []
        self.balls_velocities = []
        self.pool_ball_colors = []
        self.dropped_balls = {}
        self.is_aiming = False
        self.aim_power = 0.0
        self.finished = False
        self.result = None
        self.start_time = 0.0
        self.elapsed = 0.0

    def reset(self):
        self.ball_pos = pygame.math.Vector2(500, 250)
        self.ball_vel = pygame.math.Vector2(0, 0)
        self.balls_positions = []
        self.balls_velocities = []
        self.pool_ball_colors = list(ball_numbers_by_color.keys())
        self.dropped_balls = {}
        self.is_aiming = False
        self.aim_power = 0.0
        self.finished = False
        self.result = None
        self.start_time = time.time()
        self.elapsed = 0.0

        start_x, start_y = 250, 250
        for row in range(5):
            x = start_x - row * 26
            row_start_y = start_y - (row * 15)
            for col in range(row + 1):
                y = row_start_y + col * 30
                self.balls_positions.append(pygame.math.Vector2(x, y))
                self.balls_velocities.append(pygame.math.Vector2(0, 0))

    def remaining_colored(self):
        return len(self.balls_positions)


state = GameState()


def resolve_ball_ball_collision(pos1, vel1, pos2, vel2):
    delta = pos2 - pos1
    dist = delta.length()
    if dist == 0 or dist >= BALL_DIAMETER:
        return vel1, vel2
    normal = delta / dist
    overlap = BALL_DIAMETER - dist
    pos1 -= normal * (overlap / 2)
    pos2 += normal * (overlap / 2)

    v1n = vel1.project(normal) if vel1.length_squared() > 0 else pygame.math.Vector2(0, 0)
    v2n = vel2.project(normal) if vel2.length_squared() > 0 else pygame.math.Vector2(0, 0)

    vel1 = vel1 - v1n + v2n
    vel2 = vel2 - v2n + v1n
    return vel1, vel2


def clamp_to_board(pos, vel):
    if pos.y < BOARD_WIDTH + BALL_RADIUS:
        pos.y = BOARD_WIDTH + BALL_RADIUS
        vel.y *= -1
        cue_board_sound.play()
    elif pos.y > TABLE_HEIGHT - BOARD_WIDTH - BALL_RADIUS:
        pos.y = TABLE_HEIGHT - BOARD_WIDTH - BALL_RADIUS
        vel.y *= -1
        cue_board_sound.play()
    if pos.x < BOARD_WIDTH + BALL_RADIUS:
        pos.x = BOARD_WIDTH + BALL_RADIUS
        vel.x *= -1
        cue_board_sound.play()
    elif pos.x > TABLE_WIDTH - BOARD_WIDTH - BALL_RADIUS:
        pos.x = TABLE_WIDTH - BOARD_WIDTH - BALL_RADIUS
        vel.x *= -1
        cue_board_sound.play()
    return pos, vel


def register_result(result, elapsed):
    state.finished = True
    state.result = result
    state.elapsed = elapsed
    stats["games_played"] += 1
    if result == "WIN":
        stats["wins"] += 1
    else:
        stats["losses"] += 1
    stats["last_time"] = round(elapsed, 2)
    best = stats["best_time"]
    worst = stats["worst_time"]
    if result == "WIN":
        if best is None or elapsed < best:
            stats["best_time"] = round(elapsed, 2)
    if worst is None or elapsed > worst:
        stats["worst_time"] = round(elapsed, 2)
    save_stats(stats)


def update_physics():
    if state.finished:
        return

    state.elapsed = time.time() - state.start_time

    state.ball_pos += state.ball_vel
    state.ball_vel *= 0.98

    for pocket in pockets:
        if state.ball_pos.distance_to(pocket) < POCKET_RADIUS - 5:
            state.ball_pos = pygame.math.Vector2(400, 250)
            state.ball_vel = pygame.math.Vector2(0, 0)

    state.ball_pos, state.ball_vel = clamp_to_board(state.ball_pos, state.ball_vel)

    for i in range(len(state.balls_positions) - 1, -1, -1):
        if state.ball_pos.distance_to(state.balls_positions[i]) < BALL_DIAMETER:
            cue_stroke_ball_sound.play()
            v1 = state.ball_vel.copy()
            v2 = state.balls_velocities[i].copy()
            v1, v2 = resolve_ball_ball_collision(
                state.ball_pos, v1,
                state.balls_positions[i], v2
            )
            delta = state.balls_positions[i] - state.ball_pos
            dist = delta.length()
            if dist > 0:
                normal = delta / dist
                overlap = BALL_DIAMETER - dist
                state.balls_positions[i] += normal * (overlap / 2)
                state.ball_pos -= normal * (overlap / 2)
            state.ball_vel = v1
            state.balls_velocities[i] = v2

    for i in range(len(state.balls_positions) - 1, -1, -1):
        state.balls_positions[i] += state.balls_velocities[i]
        state.balls_velocities[i] *= 0.99
        state.balls_positions[i], state.balls_velocities[i] = clamp_to_board(
            state.balls_positions[i], state.balls_velocities[i]
        )

        potted = False
        for pocket in pockets:
            if state.balls_positions[i].distance_to(pocket) < POCKET_RADIUS - 5:
                pocket_sound.play()
                color = state.pool_ball_colors[i]
                number = ball_numbers_by_color[color]
                state.dropped_balls[color] = number
                state.balls_positions.pop(i)
                state.balls_velocities.pop(i)
                state.pool_ball_colors.pop(i)
                stats["balls_potted"] += 1
                save_stats(stats)

                if number == 8:
                    if state.remaining_colored() == 0:
                        register_result("WIN", time.time() - state.start_time)
                    else:
                        register_result("LOSS", time.time() - state.start_time)
                    return
                potted = True
                break
        if potted:
            continue

    for i in range(len(state.balls_positions)):
        for j in range(i + 1, len(state.balls_positions)):
            if state.balls_positions[i].distance_to(state.balls_positions[j]) < BALL_DIAMETER:
                delta = state.balls_positions[j] - state.balls_positions[i]
                dist = delta.length()
                if dist == 0:
                    continue
                normal = delta / dist
                overlap = BALL_DIAMETER - dist
                state.balls_positions[j] += normal * (overlap / 2)
                state.balls_positions[i] -= normal * (overlap / 2)

                v1 = state.balls_velocities[i].copy()
                v2 = state.balls_velocities[j].copy()
                v1, v2 = resolve_ball_ball_collision(
                    state.balls_positions[i], v1,
                    state.balls_positions[j], v2
                )
                state.balls_velocities[i] = v1
                state.balls_velocities[j] = v2
                cue_ball_and_ball_sound.play()


def compute_power_from_mouse(mouse_pos):
    dist = state.ball_pos.distance_to(mouse_pos)
    if dist <= 0:
        return 0.0
    power = dist * 0.15
    return clamp(power, 0.0, MAX_SHOT_POWER)


def draw_aiming():
    if not state.is_aiming or state.finished:
        return
    mouse_pos = pygame.mouse.get_pos()
    aim_vector = state.ball_pos - mouse_pos
    if aim_vector.length_squared() == 0:
        return
    direction = aim_vector.normalize()

    hit_balls = True
    target_ball = None
    hit_index = 0
    for i in range(1, 20):
        dot_pos = state.ball_pos + direction * i * 15
        if dot_pos.x < BOARD_WIDTH or dot_pos.x > TABLE_WIDTH - BOARD_WIDTH:
            break
        if dot_pos.y < BOARD_WIDTH or dot_pos.y > TABLE_HEIGHT - BOARD_WIDTH:
            break
        pygame.draw.circle(display, (245, 245, 245), dot_pos, 2)
        if hit_balls:
            for b in state.balls_positions:
                if b.distance_to(dot_pos) < 25:
                    hit_balls = False
                    target_ball = b
                    hit_index = i
                    break

    if not hit_balls and target_ball is not None:
        ball_dir = target_ball - (state.ball_pos + direction * hit_index * 15)
        if ball_dir.length_squared() > 0:
            ball_dir = ball_dir.normalize()
            for k in range(1, 20 - hit_index):
                dot_pos2 = target_ball + ball_dir * k * 12
                if dot_pos2.x < BOARD_WIDTH or dot_pos2.x > TABLE_WIDTH - BOARD_WIDTH:
                    break
                if dot_pos2.y < BOARD_WIDTH or dot_pos2.y > TABLE_HEIGHT - BOARD_WIDTH:
                    break
                pygame.draw.circle(display, (230, 230, 230), dot_pos2, 2)

    pygame.draw.line(display, (139, 90, 43), state.ball_pos, mouse_pos, 6)


def draw_ball(surface, pos, color, number=None, is_cue=False):
    x, y = int(pos.x), int(pos.y)
    base = (255, 255, 255) if is_cue else color
    pygame.draw.circle(surface, base, (x, y), BALL_RADIUS)
    pygame.draw.circle(surface, (0, 0, 0), (x, y), BALL_RADIUS, 1)
    if number is not None:
        text = ball_font.render(str(number), True, (255, 255, 255))
        rect = text.get_rect(center=(x, y))
        surface.blit(text, rect)


def draw_table():
    pygame.draw.rect(display, (46, 139, 46),
                     (BOARD_WIDTH, BOARD_WIDTH,
                      TABLE_WIDTH - BOARD_WIDTH * 2,
                      TABLE_HEIGHT - BOARD_WIDTH * 2))
    pygame.draw.rect(display, (101, 67, 33), (0, 0, TABLE_WIDTH, TABLE_HEIGHT), BOARD_WIDTH)
    for pocket in pockets:
        pygame.draw.circle(display, (0, 0, 0), pocket, POCKET_RADIUS)


def draw_score_panel():
    pygame.draw.rect(display, (120, 219, 226), game_status_rect)

    title = score_font.render("СЧЁТ", True, (20, 40, 60))
    display.blit(title, (TABLE_WIDTH + 15, 8))

    timer = small_font.render(f"Время: {format_time(state.elapsed)}", True, (20, 40, 60))
    display.blit(timer, (TABLE_WIDTH + 10, 32))

    potted = small_font.render(f"Забито: {len(state.dropped_balls)}/15", True, (20, 40, 60))
    display.blit(potted, (TABLE_WIDTH + 10, 52))

    if state.is_aiming:
        pct = state.aim_power / MAX_SHOT_POWER
        bar_x = TABLE_WIDTH + 10
        bar_y = 76
        bar_w = SIDE_PANEL_WIDTH - 20
        bar_h = 14
        pygame.draw.rect(display, (30, 60, 80), (bar_x, bar_y, bar_w, bar_h))

        fill_w = int(bar_w * pct)
        if pct < 0.5:
            color = (80, 200, 80)
        else:
            color = (230, 60, 60)
        if fill_w > 0:
            pygame.draw.rect(display, color, (bar_x, bar_y, fill_w, bar_h))

        power_text = small_font.render(f"Сила: {int(pct * 100)}%", True, (20, 40, 60))
        display.blit(power_text, (TABLE_WIDTH + 10, bar_y + bar_h + 4))

        top_y = bar_y + bar_h + 26
    else:
        top_y = 78

    dropped_x = TABLE_WIDTH + 8
    dropped_y = top_y
    i = 0
    for color, num in state.dropped_balls.items():
        if i % 2 == 0 and i != 0:
            dropped_x = TABLE_WIDTH + 8
            dropped_y += BALL_RADIUS * 2 + 6
        cx = dropped_x + BALL_RADIUS
        cy = dropped_y + BALL_RADIUS
        pygame.draw.circle(display, color, pygame.math.Vector2(cx, cy), BALL_RADIUS)
        pygame.draw.circle(display, (0, 0, 0), pygame.math.Vector2(cx, cy), BALL_RADIUS, 1)
        text = ball_font.render(str(num), True, (255, 255, 255))
        rect = text.get_rect(center=(cx, cy))
        display.blit(text, rect)
        dropped_x += BALL_RADIUS * 2 + 6
        i += 1

    if state.finished:
        if state.result == "WIN":
            msg = small_font.render("ПОБЕДА!", True, (0, 120, 0))
        else:
            msg = small_font.render("ПОРАЖЕНИЕ", True, (170, 0, 0))
        display.blit(msg, (TABLE_WIDTH + 10, HEIGHT - 80))

        t = small_font.render(format_time(state.elapsed), True, (20, 40, 60))
        display.blit(t, (TABLE_WIDTH + 10, HEIGHT - 58))

        hint = small_font.render("R / ESC", True, (20, 40, 60))
        display.blit(hint, (TABLE_WIDTH + 10, HEIGHT - 36))


def draw_game():
    display.fill(bg)
    draw_table()

    for i, ball in enumerate(state.balls_positions):
        color = state.pool_ball_colors[i]
        draw_ball(display, ball, color, ball_numbers_by_color[color])

    draw_aiming()
    draw_ball(display, state.ball_pos, (255, 255, 255), is_cue=True)
    draw_score_panel()


def draw_button(rect, text, mouse_pos, font=None):
    font = font or btn_font
    hovered = rect.collidepoint(mouse_pos)
    color = (140, 95, 50) if hovered else (101, 67, 33)
    pygame.draw.rect(display, color, rect)
    surf = font.render(text, True, (255, 255, 255))
    display.blit(surf, surf.get_rect(center=rect.center))


def main_menu_loop():
    bg_panel = pygame.Surface((560, 420), pygame.SRCALPHA)
    bg_panel.fill((211, 252, 253, 200))
    bg_panel_rect = bg_panel.get_rect(center=(WIDTH // 2, HEIGHT // 2))

    title_surf = title_font.render("БИЛЬЯРД", True, (60, 40, 20))
    title_rect = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 130))

    while True:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "QUIT"
            if event.type == pygame.MOUSEBUTTONDOWN:
                if play_btn.collidepoint(event.pos):
                    return "PLAY"
                if stats_btn.collidepoint(event.pos):
                    return "STATS"
                if exit_btn.collidepoint(event.pos):
                    return "QUIT"

        display.fill(bg)
        display.blit(bg_panel, bg_panel_rect)
        display.blit(title_surf, title_rect)
        draw_button(play_btn, "СТАРТ", mouse_pos)
        draw_button(stats_btn, "СТАТИСТИКА", mouse_pos)
        draw_button(exit_btn, "ВЫХОД", mouse_pos)
        pygame.display.update()
        clock.tick(60)


def stats_loop():
    bg_panel = pygame.Surface((640, 420), pygame.SRCALPHA)
    bg_panel.fill((211, 252, 253, 210))
    bg_panel_rect = bg_panel.get_rect(center=(WIDTH // 2, HEIGHT // 2))

    title = title_font.render("СТАТИСТИКА", True, (60, 40, 20))
    title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 170))

    line_font = pygame.font.SysFont("Arial", 22)
    left_x = WIDTH // 2 - 260
    right_x = WIDTH // 2 + 20

    def lines_for(column):
        if column == 0:
            return [
                f"Игр сыграно: {stats['games_played']}",
                f"Побед: {stats['wins']}",
                f"Поражений: {stats['losses']}",
                f"Винрейт: {winrate(stats)}",
            ]
        return [
            f"Забито шаров: {stats['balls_potted']}",
            f"Последнее время: {format_time(stats['last_time'])}",
            f"Лучшее время: {format_time(stats['best_time'])}",
            f"Худшее время: {format_time(stats['worst_time'])}",
        ]

    while True:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "QUIT"
            if event.type == pygame.MOUSEBUTTONDOWN and back_btn.collidepoint(event.pos):
                return "MENU"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "MENU"

        display.fill(bg)
        display.blit(bg_panel, bg_panel_rect)
        display.blit(title, title_rect)

        for col in range(2):
            base_x = left_x if col == 0 else right_x
            for idx, line in enumerate(lines_for(col)):
                surf = line_font.render(line, True, (40, 40, 40))
                display.blit(surf, (base_x, HEIGHT // 2 - 90 + idx * 40))

        draw_button(back_btn, "НАЗАД", mouse_pos)
        pygame.display.update()
        clock.tick(60)


def play_loop():
    state.reset()

    while True:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "QUIT"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "MENU"
                if event.key == pygame.K_r:
                    state.reset()
            if state.finished:
                continue
            if event.type == pygame.MOUSEBUTTONDOWN:
                if state.ball_pos.distance_to(mouse_pos) < 30 and state.ball_vel.length() < 0.2:
                    state.is_aiming = True
                    state.aim_power = compute_power_from_mouse(mouse_pos)
            elif event.type == pygame.MOUSEMOTION and state.is_aiming:
                state.aim_power = compute_power_from_mouse(mouse_pos)
            elif event.type == pygame.MOUSEBUTTONUP and state.is_aiming:
                power = compute_power_from_mouse(mouse_pos)
                aim_vec = state.ball_pos - mouse_pos
                if aim_vec.length_squared() > 0:
                    direction = aim_vec.normalize()
                    state.ball_vel = direction * power
                cue_stroke_sound.play()
                state.is_aiming = False
                state.aim_power = 0.0

        update_physics()
        draw_game()
        pygame.display.update()
        clock.tick(60)


def main():
    scene = "MENU"
    while True:
        if scene == "MENU":
            scene = main_menu_loop()
        elif scene == "STATS":
            scene = stats_loop()
        elif scene == "PLAY":
            scene = play_loop()
        elif scene == "QUIT":
            break
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()