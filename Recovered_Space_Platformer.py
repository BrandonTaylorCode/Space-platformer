# ===========================
# SPACE PLATFORMER – SURGICALLY FIXED FOR PYCHARM
# ===========================

import pygame
import sys
import random
import math
from pathlib import Path

pygame.init()
pygame.mixer.init()

# ---------------------------
# Virtual resolution
# ---------------------------
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = 970, 1600
info = pygame.display.Info()
SCREEN_WIDTH = min(info.current_w, 1000)
SCREEN_HEIGHT = min(info.current_h, 1800)
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Space Platformer")
render_surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))
clock = pygame.time.Clock()
WORLD_WIDTH = VIRTUAL_WIDTH * 8

# ---------------------------
# Colors
# ---------------------------
BLACK = (0, 0, 0)
WHITE = (245, 245, 245)
BLUE = (50, 150, 255)
ORANGE = (255, 140, 0)
RED = (220, 60, 60)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 100)
SHIP_COLOR = (200, 200, 255)
PURPLE = (160, 80, 255)

# ---------------------------
# Physics
# ---------------------------
GRAVITY = 0.5
THRUST = -1.0
MAX_FALL_SPEED = 24
SCROLL_SPEED = 6
font = pygame.font.SysFont(None, 72)

# ---------------------------
# Sound Loader
# ---------------------------
def load_sound(name):
    try:
        return pygame.mixer.Sound(name)
    except:
        return None

jump_snd = load_sound("jump.wav")
explode_snd = load_sound("explode.wav")
boss_snd = load_sound("boss.wav")

# ---------------------------
# Highscores
# ---------------------------
HIGHSCORE_FILE = "highscores.txt"
TOP_SCORES = 5

def load_highscores():
    if not Path(HIGHSCORE_FILE).exists():
        return []
    with open(HIGHSCORE_FILE) as f:
        scores = []
        for line in f:
            try: scores.append(int(line.strip()))
            except: pass
    return sorted(scores, reverse=True)[:TOP_SCORES]

def save_highscore(score):
    scores = load_highscores()
    scores.append(score)
    scores = sorted(scores, reverse=True)[:TOP_SCORES]
    with open(HIGHSCORE_FILE, "w") as f:
        for s in scores:
            f.write(f"{s}\n")
    return scores

# ---------------------------
# Starfield
# ---------------------------
def generate_starfield(count):
    return [[random.randint(0, WORLD_WIDTH),
             random.randint(0, VIRTUAL_HEIGHT),
             random.randint(2, 6)] for _ in range(count)]

star_layers = [
    {"stars": generate_starfield(300), "speed": 0.3, "color": WHITE},
    {"stars": generate_starfield(300), "speed": 0.6, "color": (200, 200, 255)},
    {"stars": generate_starfield(300), "speed": 1.0, "color": YELLOW},
]

# ---------------------------
# Game State
# ---------------------------
def reset_game():
    global player, velocity_y, obstacles, bosses, bullets, boss_bullets
    global particles, boss_flashes, score, game_over, scroll_x
    global last_obstacle_x, score_saved, last_boss_score
    global player_cooldown, shooting, camera_shake

    player = pygame.Rect(240, VIRTUAL_HEIGHT // 2, 120, 80)
    velocity_y = 0
    scroll_x = 0
    obstacles = []
    bosses = []
    bullets = []
    boss_bullets = []
    particles = []
    boss_flashes = []
    score = 0
    game_over = False
    last_obstacle_x = VIRTUAL_WIDTH
    score_saved = False
    last_boss_score = 0
    player_cooldown = 0
    shooting = False
    camera_shake = 0

# ---------------------------
# Asteroids
# ---------------------------
def spawn_asteroid(x):
    h = random.randint(160, 340)
    w = int(h * random.uniform(0.8, 1.0))
    y = random.randint(120, VIRTUAL_HEIGHT - h - 120)
    angle = random.uniform(0, math.tau)
    speed = random.uniform(1.5, 3)
    return {
        "rect": pygame.Rect(x, y, w, h),
        "vx": math.cos(angle) * speed,
        "vy": math.sin(angle) * speed,
        "rot": random.randint(0, 360),
        "rot_spd": random.uniform(-3, 3),
        "shape": None
    }

def breakup_asteroid(a):
    count = random.randint(2, 4)
    small_asteroids = []
    for _ in range(count):
        w = int(a["rect"].width * random.uniform(0.3, 0.6))
        h = int(a["rect"].height * random.uniform(0.3, 0.6))
        x = a["rect"].x + random.randint(-w//2, w//2)
        y = a["rect"].y + random.randint(-h//2, h//2)
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1, 2.5)
        small_asteroids.append({
            "rect": pygame.Rect(x, y, w, h),
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "rot": random.randint(0, 360),
            "rot_spd": random.uniform(-3, 3),
            "shape": None
        })
    return small_asteroids

# ---------------------------
# Boss
# ---------------------------
def spawn_boss(x):
    if boss_snd: boss_snd.play()
    hp = 20 + int(scroll_x / 2500) * 5
    return {
        "rect": pygame.Rect(x, VIRTUAL_HEIGHT // 2 - 220, 140, 440),
        "hp": hp,
        "max_hp": hp,
        "cooldown": 0
    }

# ---------------------------
# Effects
# ---------------------------
def spawn_particles(pos):
    if explode_snd: explode_snd.play()
    for _ in range(24):
        particles.append({
            "x": pos[0], "y": pos[1],
            "vx": random.uniform(-5, 5),
            "vy": random.uniform(-5, 5),
            "life": 30
        })

# ---------------------------
# Bullets
# ---------------------------
BULLET_SPEED = 15
PLAYER_FIRE_COOLDOWN = 8
boss_bullets = []

# ---------------------------
# Spaceship drawing
# ---------------------------
def draw_spaceship(surface, rect, thrusting=False):
    cx, cy = rect.center
    # Main body (pointed nose)
    body_points = [
        (rect.left, cy - rect.height // 2),
        (rect.left, cy + rect.height // 2),
        (rect.right, cy)
    ]
    pygame.draw.polygon(surface, SHIP_COLOR, body_points)

    # Tail fins
    pygame.draw.polygon(surface, SHIP_COLOR, [
        (rect.left, cy - rect.height // 2),
        (rect.left - rect.width // 4, cy - rect.height // 2 - 10),
        (rect.left, cy - rect.height // 2 + 10)
    ])
    pygame.draw.polygon(surface, SHIP_COLOR, [
        (rect.left, cy + rect.height // 2),
        (rect.left - rect.width // 4, cy + rect.height // 2 + 10),
        (rect.left, cy + rect.height // 2 - 10)
    ])

    # Thrust flame
    if thrusting:
        pygame.draw.polygon(surface, ORANGE, [
            (rect.left - 30, cy - 20),
            (rect.left - 30, cy + 20),
            (rect.left, cy)
        ])

# ---------------------------
# Asteroid drawing
# ---------------------------
def draw_asteroid(surface, a, color=ORANGE):
    if not a["shape"]:
        rect = a["rect"]
        cx, cy = rect.center
        pts = []
        for i in range(8):
            ang = math.radians(i * 45)
            rx = rect.width / 2 * random.uniform(0.85, 1.15)
            ry = rect.height / 2 * random.uniform(0.9, 1.1)
            pts.append((rx * math.cos(ang), ry * math.sin(ang)))
        a["shape"] = pts

    pts = [(a["rect"].centerx + x, a["rect"].centery + y) for x, y in a["shape"]]
    pygame.draw.polygon(surface, color, pts)

# ---------------------------
# Setup
# ---------------------------
reset_game()
top = []  # initialize top scores list

running = True
touching = False
MAX_OBSTACLE_AHEAD = VIRTUAL_WIDTH * 3

# ---------------------------
# Main loop
# ---------------------------
while running:
    # --- GLOBAL DECLARATION FOR PYCHARM ---
    global score, scroll_x, velocity_y, player, bullets, obstacles
    global bosses, particles, player_cooldown, shooting, camera_shake
    global last_obstacle_x, last_boss_score, score_saved, top

    clock.tick(60)
    render_surface.fill(BLACK)

    # Starfield
    for layer in star_layers:
        for s in layer["stars"]:
            x = (s[0] - scroll_x * layer["speed"]) % WORLD_WIDTH
            pygame.draw.circle(render_surface, layer["color"], (int(x), s[1]), s[2])

    # Input
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        if e.type == pygame.MOUSEBUTTONDOWN:
            touching = True
            if game_over: reset_game()
        if e.type == pygame.MOUSEBUTTONUP:
            touching = False
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_SPACE:
                touching = True
                if game_over: reset_game()
            if e.key == pygame.K_LSHIFT:
                shooting = True
        if e.type == pygame.KEYUP:
            if e.key == pygame.K_SPACE:
                touching = False
            if e.key == pygame.K_LSHIFT:
                shooting = False

    thrusting = touching or pygame.key.get_pressed()[pygame.K_SPACE]

    # Shooting
    if shooting and not game_over and player_cooldown <= 0:
        bullets.append(pygame.Rect(player.right, player.centery - 2, 12, 4))
        player_cooldown = PLAYER_FIRE_COOLDOWN
    if player_cooldown > 0:
        player_cooldown -= 1

    # ---------------------------
    # GAME LOGIC
    # ---------------------------
    if not game_over:
        velocity_y += THRUST if thrusting else GRAVITY
        velocity_y = min(velocity_y, MAX_FALL_SPEED)
        player.y += velocity_y
        scroll_x += SCROLL_SPEED
        score += 1

        # Spawn asteroids
        while last_obstacle_x < scroll_x + MAX_OBSTACLE_AHEAD:
            a = spawn_asteroid(last_obstacle_x)
            obstacles.append(a)
            last_obstacle_x = a["rect"].x + random.randint(150, 250)

        # Boss spawn
        if score >= last_boss_score + 2500:
            bosses.append(spawn_boss(VIRTUAL_WIDTH + 200))
            last_boss_score = score

        # Update asteroids
        for a in obstacles:
            a["rect"].x += int(a["vx"]) - SCROLL_SPEED
            a["rect"].y += int(a["vy"])

        # Update bullets
        for b in bullets[:]:
            b.x += BULLET_SPEED

            # Asteroid collision
            for a in obstacles[:]:
                if b.colliderect(a["rect"].inflate(-a["rect"].w * 0.2, -a["rect"].h * 0.2)):
                    spawn_particles(b.center)
                    bullets.remove(b)
                    obstacles.remove(a)
                    obstacles.extend(breakup_asteroid(a))
                    break

            # Boss collision
            for boss in bosses[:]:
                if b.colliderect(boss["rect"]):
                    bullets.remove(b)
                    boss["hp"] -= 1
                    spawn_particles(b.center)
                    if boss["hp"] <= 0:
                        bosses.remove(boss)
                        spawn_particles(boss["rect"].center)
                    break

            if b.x > VIRTUAL_WIDTH and b in bullets:
                bullets.remove(b)

        # Player collision
        hitbox = player.inflate(-player.w * 0.3, -player.h * 0.3)
        for a in obstacles:
            if hitbox.colliderect(a["rect"]):
                spawn_particles(player.center)
                camera_shake = 6
                game_over = True

        if player.top < 0 or player.bottom > VIRTUAL_HEIGHT:
            game_over = True

    # ---------------------------
    # Rendering
    # ---------------------------
    for a in obstacles:
        draw_asteroid(render_surface, a)

    for boss in bosses:
        # Draw boss
        pygame.draw.rect(render_surface, PURPLE, boss["rect"])
        # Draw HP bar
        bar_width = boss["rect"].width
        bar_height = 10
        hp_ratio = boss["hp"] / boss["max_hp"]
        pygame.draw.rect(render_surface, RED, (boss["rect"].x, boss["rect"].y - 20, bar_width, bar_height))
        pygame.draw.rect(render_surface, GREEN, (boss["rect"].x, boss["rect"].y - 20, int(bar_width * hp_ratio), bar_height))

    for b in bullets:
        pygame.draw.rect(render_surface, BLUE, b)

    for p in particles[:]:
        p["x"] += p["vx"]
        p["y"] += p["vy"]
        p["life"] -= 1
        pygame.draw.circle(render_surface, ORANGE, (int(p["x"]), int(p["y"])), 3)
        if p["life"] <= 0:
            particles.remove(p)

    draw_spaceship(render_surface, player, thrusting)
    render_surface.blit(font.render(f"Score: {score}", True, YELLOW), (20, 20))

    if game_over:
        if not score_saved:
            top = save_highscore(score)
            score_saved = True
        render_surface.blit(font.render("GAME OVER", True, RED), (350, 700))
        for i, s in enumerate(top):
            render_surface.blit(font.render(f"{i+1}. {s}", True, YELLOW), (420, 820 + i * 70))

    shake_x = random.randint(-camera_shake, camera_shake) if camera_shake else 0
    shake_y = random.randint(-camera_shake, camera_shake) if camera_shake else 0
    camera_shake = max(0, camera_shake - 1)

    scaled = pygame.transform.smoothscale(render_surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled, (shake_x, shake_y))
    pygame.display.flip()

pygame.quit()
sys.exit()

