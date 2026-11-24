"""Space Platformer -- standalone version for VS Code or any Python editor.

Install pygame in your selected Python environment, then run this file.
Controls: Space / left mouse = thrust; Left Shift / right mouse = shoot.
Touch: hold the left half to thrust and the right half to fire. Use both together.
After game over, press Space or click/tap to restart. Escape closes the game.
Optional jump.wav, explode.wav and boss.wav belong beside this file.
High scores are saved to highscores.txt beside this file.
"""

from array import array
from io import BytesIO
import sys
import wave
import math
import random
from pathlib import Path

import pygame


# ---------------------------
# Display, colors and physics
# ---------------------------
VIRTUAL_WIDTH, VIRTUAL_HEIGHT = 970, 1600
WORLD_WIDTH = VIRTUAL_WIDTH * 8
FPS = 60
GRAVITY = 0.44
THRUST = -1.0
MAX_FALL_SPEED = 24
SCROLL_SPEED = 6
BULLET_SPEED = 15
BOSS_BULLET_SPEED = 10
PLAYER_FIRE_COOLDOWN = 8
BOSS_FIRE_COOLDOWN = 90
BOSS_SCORE_INTERVAL = 2500
MAX_OBSTACLE_AHEAD = VIRTUAL_WIDTH * 3
MIN_FRAGMENT_SIZE = 48
MAX_FRAGMENT_GENERATION = 2

BLACK = (0, 0, 0)
WHITE = (245, 245, 245)
BLUE = (50, 150, 255)
ORANGE = (255, 140, 0)
RED = (220, 60, 60)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 100)
SHIP_COLOR = (200, 200, 255)
PURPLE = (160, 80, 255)

BASE_DIR = Path(__file__).resolve().parent
HIGHSCORE_FILE = BASE_DIR / "highscores.txt"
TOP_SCORES = 5
jump_snd = explode_snd = boss_snd = laser_snd = enemy_snd = None


def load_sound(name):
    """Missing files or unavailable audio must not stop the game."""
    if pygame.mixer.get_init() is None:
        return None
    try:
        return pygame.mixer.Sound(str(BASE_DIR / name))
    except (pygame.error, OSError):
        return None


def synth_effect(start_hz, end_hz, seconds, noise, volume):
    """Build one short mono effect at startup. SDL converts it to the output format."""
    if not pygame.mixer.get_init():
        return None
    rate = 22050
    count = round(rate * seconds)
    samples = array("h")
    rng = random.Random(29)
    phase = rumble = 0.0
    for i in range(count):
        progress = i / count
        phase += math.tau * (start_hz + (end_hz - start_hz) * progress) / rate
        rumble = 0.72 * rumble + 0.28 * rng.uniform(-1, 1)
        signal = (1 - noise) * math.sin(phase) + noise * rumble
        envelope = min(1, i / 100) * (1 - progress) ** 1.6
        samples.append(round(32767 * volume * envelope * signal))
    if sys.byteorder != "little":
        samples.byteswap()
    audio = BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, rate, count, "NONE", "not compressed"))
        wav.writeframes(samples.tobytes())
    audio.seek(0)
    return pygame.mixer.Sound(file=audio)


def start_space_theme():
    """Score an eight-bar orbital waltz and loop it on the music channel."""
    if not pygame.mixer.get_init():
        return
    rate = 12000
    beat = 9000  # 80 BPM, three beats per bar
    chords = [(57, 60, 64), (53, 57, 60), (60, 64, 67), (55, 59, 62),
              (57, 60, 64), (53, 57, 60), (50, 53, 57), (52, 56, 59)]
    melody = [(76, 79, 81), (77, 0, 76), (76, 79, 83), (81, 0, 79),
              (76, 79, 84), (81, 0, 77), (77, 76, 74), (71, 0, 68)]
    mix = array("f", [0]) * (len(chords) * 3 * beat)
    cache = {}

    def note(start, pitch, length, gain, attack, release):
        key = (pitch, length, attack, release)
        if key not in cache:
            phase_step = math.tau * 440 * 2 ** ((pitch - 69) / 12) / rate
            cache[key] = array("f", (
                (math.sin(i * phase_step) + 0.17 * math.sin(2 * i * phase_step))
                * min(1, i / attack, (length - 1 - i) / release)
                for i in range(length)))
        for i, sample in enumerate(cache[key]):
            mix[start + i] += gain * sample

    for bar, chord in enumerate(chords):
        start = bar * 3 * beat
        for pitch in chord:
            note(start, pitch, 3 * beat, 0.064, 2200, 3200)
        note(start, chord[0] - 12, beat, 0.16, 120, 5500)
        for pulse, pitch in enumerate(melody[bar]):
            onset = start + pulse * beat
            note(onset + beat // 2, chord[pulse] + 12, beat // 2, 0.055, 70, 4200)
            if pitch:
                length = 2 * beat if pulse == 0 and melody[bar][1] == 0 else beat
                note(onset, pitch, length, 0.21, 350, 2400)
    samples = array("h", (round(value * 32767) for value in mix))
    if sys.byteorder != "little":
        samples.byteswap()
    audio = BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, rate, len(samples), "NONE", "not compressed"))
        wav.writeframes(samples.tobytes())
    audio.seek(0)
    sound = pygame.mixer.Sound(file=audio)
    sound.set_volume(0.45)
    pygame.mixer.set_reserved(1)
    pygame.mixer.Channel(0).play(sound, loops=-1, fade_ms=900)


def play_sound(sound):
    if sound is not None and pygame.mixer.get_init() is not None:
        try:
            sound.play()
        except pygame.error:
            pass


def load_highscores():
    try:
        lines = HIGHSCORE_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    scores = []
    for line in lines:
        try:
            value = int(line.strip())
        except ValueError:
            continue
        if value >= 0:
            scores.append(value)
    return sorted(scores, reverse=True)[:TOP_SCORES]


def save_highscore(value):
    scores = sorted(load_highscores() + [value], reverse=True)[:TOP_SCORES]
    try:
        HIGHSCORE_FILE.write_text("".join(f"{s}\n" for s in scores), encoding="utf-8")
    except OSError as error:
        print(f"Could not save high scores: {error}")
        return scores, False
    return scores, True


def generate_starfield(count):
    return [[random.randrange(WORLD_WIDTH), random.randrange(VIRTUAL_HEIGHT),
             random.randint(2, 6)] for _ in range(count)]


# ---------------------------
# Game state
# ---------------------------
def reset_game():
    global player, player_y, velocity_y, obstacles, bosses, bullets, boss_bullets
    global particles, point_labels, score, game_over, scroll_x, last_obstacle_x
    global last_boss_score, player_cooldown, camera_shake, score_saved
    global top, score_write_ok

    player = pygame.Rect(240, VIRTUAL_HEIGHT // 2, 120, 80)
    player_y = float(player.y)
    velocity_y = 0.0
    scroll_x = 0
    obstacles, bosses, bullets, boss_bullets, particles = [], [], [], [], []
    point_labels = []
    score = 0
    game_over = False
    last_obstacle_x = VIRTUAL_WIDTH  # This cursor is in WORLD coordinates.
    last_boss_score = 0
    player_cooldown = 0
    camera_shake = 0
    score_saved = False
    score_write_ok = True
    top = load_highscores()


def make_asteroid(rect, speed_range, generation=0):
    angle = random.uniform(0, math.tau)
    speed = random.uniform(*speed_range)
    shape = []
    sides = random.randint(8, 13)
    for i in range(sides):
        angle_i = (i + random.uniform(-0.18, 0.18)) * math.tau / sides
        rx = rect.width / 2 * random.uniform(0.85, 1.15)
        ry = rect.height / 2 * random.uniform(0.9, 1.1)
        shape.append((rx * math.cos(angle_i), ry * math.sin(angle_i)))
    return {
        "rect": rect, "x": float(rect.x), "y": float(rect.y),
        "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
        "rot": random.uniform(0, 360), "rot_spd": random.uniform(-3, 3),
        "tone": random.choice([(181, 108, 59), (159, 116, 82), (173, 133, 96)]),
        "craters": [(random.uniform(-0.23, 0.23) * rect.w, random.uniform(-0.23, 0.23) * rect.h,
                     random.uniform(0.04, 0.09) * min(rect.size)) for _ in range(random.randint(2, 5))],
        "phase": random.uniform(0, math.tau),
        "shape": shape, "generation": generation,
    }


def spawn_asteroid(screen_x):
    height = random.randint(160, 340)
    width = int(height * random.uniform(0.8, 1.0))
    y = random.randint(120, VIRTUAL_HEIGHT - height - 120)
    return make_asteroid(pygame.Rect(screen_x, y, width, height), (1.5, 3))


def breakup_asteroid(asteroid):
    # Small pieces disappear when shot; they cannot split forever.
    if asteroid["generation"] >= MAX_FRAGMENT_GENERATION:
        return []
    rect = asteroid["rect"]
    fragments = []
    for _ in range(random.randint(2, 4)):
        width = int(rect.width * random.uniform(0.3, 0.6))
        height = int(rect.height * random.uniform(0.3, 0.6))
        if min(width, height) < MIN_FRAGMENT_SIZE:
            continue
        piece = pygame.Rect(0, 0, width, height)
        piece.center = (rect.centerx + random.randint(-width // 2, width // 2),
                        rect.centery + random.randint(-height // 2, height // 2))
        fragments.append(make_asteroid(piece, (1, 2.5), asteroid["generation"] + 1))
    return fragments


def spawn_boss(screen_x):
    play_sound(boss_snd)
    hp = 20 + int(scroll_x / 2500) * 5
    return {"rect": pygame.Rect(screen_x, VIRTUAL_HEIGHT // 2 - 220, 140, 440),
            "hp": hp, "max_hp": hp, "cooldown": BOSS_FIRE_COOLDOWN,
            "phase": 0.0}


def spawn_particles(pos):
    play_sound(explode_snd)
    for _ in range(24):
        particles.append({"x": float(pos[0]), "y": float(pos[1]),
                          "vx": random.uniform(-5, 5), "vy": random.uniform(-5, 5),
                          "life": 30})


def end_game():
    global game_over, camera_shake
    if not game_over:
        game_over = True
        camera_shake = 6
        spawn_particles(player.center)


def update_player_bullets():
    """Each shot can hit ONE target and is removed only once."""
    global score
    remaining = []
    fragments = []
    for bullet in bullets:
        bullet.x += BULLET_SPEED
        consumed = False
        for asteroid in obstacles[:]:
            if asteroid_hits(asteroid, bullet):
                spawn_particles(bullet.center)
                obstacles.remove(asteroid)
                rect = asteroid['rect']
                # Halving both dimensions doubles the reward for the smaller target.
                points = max(1, round(10000 / math.sqrt(rect.width * rect.height)))
                score += points
                point_labels.append((bullet.centerx, bullet.centery, points, 48))
                fragments.extend(breakup_asteroid(asteroid))
                consumed = True
                break
        if not consumed:
            for boss in bosses[:]:
                if bullet.colliderect(boss["rect"]):
                    boss["hp"] -= 1
                    spawn_particles(bullet.center)
                    if boss["hp"] <= 0:
                        bosses.remove(boss)
                        spawn_particles(boss["rect"].center)
                    consumed = True
                    break
        if not consumed and bullet.left <= VIRTUAL_WIDTH:
            remaining.append(bullet)
    bullets[:] = remaining
    obstacles.extend(fragments)


def update_bosses():
    for boss in bosses:
        rect = boss["rect"]
        target_x = VIRTUAL_WIDTH - rect.width - 100
        rect.x = max(target_x, rect.x - 3)
        boss["phase"] += 0.025
        rect.centery = VIRTUAL_HEIGHT // 2 + int(math.sin(boss["phase"]) * 300)
        if rect.right > VIRTUAL_WIDTH:
            continue  # Enter the screen before firing.
        boss["cooldown"] -= 1
        if boss["cooldown"] <= 0:
            position = pygame.Vector2(rect.midleft)
            direction = pygame.Vector2(player.center) - position
            if direction.length_squared() == 0:
                direction = pygame.Vector2(-1, 0)
            velocity = direction.normalize() * BOSS_BULLET_SPEED
            shot_rect = pygame.Rect(0, 0, 16, 16)
            shot_rect.center = (round(position.x), round(position.y))
            play_sound(enemy_snd)
            boss_bullets.append({"rect": shot_rect, "pos": position, "vel": velocity})
            boss["cooldown"] = BOSS_FIRE_COOLDOWN

    for shot in boss_bullets:
        shot["pos"] += shot["vel"]
        shot["rect"].center = (round(shot["pos"].x), round(shot["pos"].y))
    bounds = pygame.Rect(-100, -100, VIRTUAL_WIDTH + 200, VIRTUAL_HEIGHT + 200)
    boss_bullets[:] = [shot for shot in boss_bullets if bounds.colliderect(shot["rect"])]


def update_game(thrusting, shooting):
    """Advance one 1/60-second physics step, independent of rendering."""
    global velocity_y, player_y, scroll_x, score, player_cooldown
    global last_obstacle_x, last_boss_score, camera_shake

    camera_shake = max(0, camera_shake - 1)
    if not game_over:
        if player_cooldown > 0:
            player_cooldown -= 1
        if shooting and player_cooldown == 0:
            play_sound(laser_snd)
            bullets.append(pygame.Rect(player.right, player.centery - 2, 12, 4))
            player_cooldown = PLAYER_FIRE_COOLDOWN

        velocity_y = min(velocity_y + (THRUST if thrusting else GRAVITY), MAX_FALL_SPEED)
        player_y += velocity_y
        player.y = round(player_y)
        scroll_x += SCROLL_SPEED


        for asteroid in obstacles:
            asteroid["x"] += asteroid["vx"] - SCROLL_SPEED
            asteroid["phase"] += 0.018
            asteroid["y"] += asteroid["vy"] + 0.75 * math.sin(asteroid["phase"])
            asteroid["rot"] = (asteroid["rot"] + asteroid["rot_spd"]) % 360
            asteroid["rect"].topleft = (round(asteroid["x"]), round(asteroid["y"]))
        obstacles[:] = [a for a in obstacles if a["rect"].right >= -400
                        and a["rect"].bottom >= -400
                        and a["rect"].top <= VIRTUAL_HEIGHT + 400]

        while last_obstacle_x < scroll_x + MAX_OBSTACLE_AHEAD:
            # New objects already include this step's scroll in their position.
            obstacles.append(spawn_asteroid(last_obstacle_x - scroll_x))
            last_obstacle_x += random.randint(150, 250)

        update_player_bullets()
        while score >= last_boss_score + BOSS_SCORE_INTERVAL:
            bosses.append(spawn_boss(VIRTUAL_WIDTH + 200))
            last_boss_score += BOSS_SCORE_INTERVAL
        update_bosses()
        hitbox = player.inflate(-int(player.w * 0.3), -int(player.h * 0.3))
        if (player.top < 0 or player.bottom > VIRTUAL_HEIGHT
                or any(asteroid_hits(a, hitbox) for a in obstacles)
                or any(hitbox.colliderect(b["rect"]) for b in bosses)
                or any(hitbox.colliderect(b["rect"]) for b in boss_bullets)):
            end_game()

    point_labels[:] = [(x, y - 1, points, life - 1) for x, y, points, life in point_labels if life > 1]
    for particle in particles:
        particle["x"] += particle["vx"]
        particle["y"] += particle["vy"]
        particle["life"] -= 1
    particles[:] = [p for p in particles if p["life"] > 0]


# ---------------------------
# Drawing
# ---------------------------
def draw_spaceship(surface, rect, thrusting=False):
    # Hull coordinates use a 120 by 80 plan view, with the nose facing right.
    def panel(color, vertices):
        points = [(rect.left + round(x * rect.w / 120),
                   rect.top + round(y * rect.h / 80)) for x, y in vertices]
        pygame.draw.polygon(surface, color, points)

    for side in (1, -1):
        def mirrored(color, vertices):
            panel(color, [(x, 40 + side * y) for x, y in vertices])

        # Swept wing, raised leading edge, and amber identification stripe.
        mirrored((53, 66, 83), [(76, 6), (50, 23), (16, 40), (6, 38), (24, 12), (18, 6)])
        mirrored((149, 165, 178), [(76, 6), (49, 21), (12, 38), (18, 31), (51, 12)])
        mirrored((235, 154, 65), [(30, 22), (34, 20), (23, 33), (17, 36)])
        # Twin nacelles sit above the wing roots.
        mirrored((69, 81, 94), [(6, 10), (48, 10), (61, 15), (48, 21), (7, 21), (2, 18)])
        mirrored((179, 191, 195), [(10, 11), (46, 11), (55, 15), (10, 15)])
        mirrored((38, 45, 56), [(4, 10), (12, 10), (12, 21), (4, 21)])
        mirrored((98, 208, 243), [(3, 12), (6, 12), (6, 19), (3, 19)])
        if thrusting:
            length = 21 + round(4 * math.sin(pygame.time.get_ticks() * 0.024))
            mirrored((50, 139, 241), [(3, 11), (-length, 16), (3, 21)])
            mirrored((194, 250, 255), [(3, 13), (-length // 2, 16), (3, 19)])

    # Light and shadow meet along the spine of the tapered fuselage.
    panel((77, 93, 109), [(7, 32), (38, 24), (83, 27), (119, 39),
                          (119, 41), (83, 53), (38, 56), (7, 48)])
    panel((201, 211, 213), [(9, 32), (39, 25), (82, 28), (118, 39), (78, 41), (25, 40)])
    panel((135, 150, 161), [(25, 40), (118, 40), (81, 48), (37, 51)])
    for x in (17, 23, 29):
        panel((52, 64, 78), [(x, 33), (x + 3, 32), (x + 5, 38), (x + 2, 39)])
    # Dark canopy frame, inset blue glass, and a narrow reflection.
    panel((32, 46, 59), [(45, 39), (53, 30), (71, 30), (90, 39), (73, 48), (53, 48)])
    panel((48, 138, 163), [(49, 39), (55, 32), (70, 32), (85, 39), (71, 45), (55, 45)])
    panel((168, 235, 241), [(53, 37), (56, 33), (69, 33), (75, 36), (59, 36)])


def rotated_point(asteroid, x, y):
    angle = math.radians(asteroid["rot"])
    cosine, sine = math.cos(angle), math.sin(angle)
    cx, cy = asteroid["rect"].center
    return round(cx + x * cosine - y * sine), round(cy + x * sine + y * cosine)


def asteroid_hits(asteroid, target):
    rect = asteroid["rect"]
    if abs(rect.centerx - target.centerx) > max(rect.size) + target.w:
        return False
    points = [rotated_point(asteroid, *pt) for pt in asteroid["shape"]]
    # The outline is star-shaped around its center. Test its edges, then
    # handle the case where the target lies entirely inside the outline.
    x, y = target.center
    inside = False
    previous = points[-1]
    for current in points:
        if target.clipline(previous, current):
            return True
        ax, ay = previous
        bx, by = current
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
        previous = current
    return inside


def draw_asteroid(surface, asteroid):
    points = [rotated_point(asteroid, *pt) for pt in asteroid["shape"]]
    center = asteroid["rect"].center
    tone = asteroid["tone"]
    for i, tip in enumerate(points):
        neighbor = points[i - 1]
        light = 1 - 0.22 * ((tip[0] - center[0]) + (tip[1] - center[1])) / max(asteroid["rect"].size)
        shade = tuple(min(255, round(channel * light)) for channel in tone)
        pygame.draw.polygon(surface, shade, [center, neighbor, tip])
    for x, y, radius in asteroid["craters"]:
        cx, cy = rotated_point(asteroid, x, y)
        r = max(2, round(radius))
        pygame.draw.circle(surface, (203, 153, 105), (cx, cy), r)
        pygame.draw.circle(surface, (104, 74, 59), (cx, cy - 1), max(1, r - 1))


def centered_text(surface, font, text, color, y):
    label = font.render(text, True, color)
    surface.blit(label, label.get_rect(center=(VIRTUAL_WIDTH // 2, y)))


def draw_boss(surface, boss):
    """Twin armored wings wrap around a broadside cannon facing the player."""
    rect = boss["rect"]
    def plate(color, points):
        pygame.draw.polygon(surface, color, [(rect.left + x, rect.centery + y) for x, y in points])

    pulse = (1 + math.sin(pygame.time.get_ticks() / 140)) / 2
    for side in (-1, 1):
        def wing(color, points):
            plate(color, [(x, side * y) for x, y in points])

        # Each outer engine sits beneath an overlapping stack of armor plates.
        wing((95, 55, 157), [(112, 132), (136, 138), (139, 185), (115, 198)])
        wing((223, 129, 255), [(129, 145), (137, 148), (137, 178), (129, 182)])
        wing((53, 44, 83), [(16, 14), (47, 62), (26, 144), (5, 200),
                             (15, 219), (75, 205), (121, 170), (131, 63), (104, 10)])
        wing((125, 99, 166), [(12, 201), (35, 140), (57, 80), (83, 72),
                               (70, 159), (40, 193)])
        wing((83, 66, 121), [(44, 195), (78, 160), (90, 72), (121, 62), (112, 158)])
        wing((205, 181, 221), [(13, 202), (51, 95), (57, 89), (32, 166)])
        for offset in (82, 105, 128):
            wing((204, 104, 242), [(89, offset), (109, offset - 9),
                                     (108, offset - 4), (88, offset + 5)])
    plate((70, 63, 95), [(6, -18), (48, -62), (100, -52), (137, -29),
                           (137, 29), (100, 52), (48, 62), (6, 18)])
    plate((143, 127, 168), [(14, -15), (51, -52), (99, -44), (126, -28), (83, -14)])
    core = (rect.left + 79, rect.centery)
    pygame.draw.circle(surface, (37, 28, 57), core, 28)
    pygame.draw.circle(surface, (148, 89, 197), core, 23, 4)
    pygame.draw.circle(surface, (235, int(96 + 62 * pulse), 207), core, 13)
    plate((37, 33, 52), [(0, -11), (52, -16), (63, -9), (63, 9), (52, 16), (0, 11)])
    plate((169, 144, 180), [(4, -10), (50, -13), (54, -7), (4, -5)])
    pygame.draw.line(surface, (255, 139, 168), (rect.left, rect.centery - 7),
                     (rect.left, rect.centery + 7), 4)


def draw_game(surface, font, small_font, star_layers, thrusting):
    surface.fill(BLACK)
    for layer in star_layers:
        for star_x, star_y, radius in layer["stars"]:
            x = (star_x - scroll_x * layer["speed"]) % WORLD_WIDTH
            if x < VIRTUAL_WIDTH + radius:
                pygame.draw.circle(surface, layer["color"], (round(x), star_y), radius)
    for asteroid in obstacles:
        rect = asteroid["rect"]
        if -400 < rect.centerx < VIRTUAL_WIDTH + 400:
            draw_asteroid(surface, asteroid)
    for boss in bosses:
        rect = boss["rect"]
        draw_boss(surface, boss)
        pygame.draw.rect(surface, RED, (rect.x, rect.y - 20, rect.width, 10))
        pygame.draw.rect(surface, GREEN,
                         (rect.x, rect.y - 20, int(rect.width * boss["hp"] / boss["max_hp"]), 10))
    for bullet in bullets:
        pygame.draw.rect(surface, BLUE, bullet)
    for shot in boss_bullets:
        pygame.draw.ellipse(surface, RED, shot["rect"])
    for particle in particles:
        pygame.draw.circle(surface, ORANGE, (round(particle["x"]), round(particle["y"])), 3)
    draw_spaceship(surface, player, thrusting and not game_over)
    for x, y, points, _ in point_labels:
        label = small_font.render(f"+{points}", True, YELLOW)
        surface.blit(label, label.get_rect(center=(x, y)))
    surface.blit(font.render(f"Score: {score}", True, YELLOW), (20, 20))
    for label, x in (("LEFT: THRUST", VIRTUAL_WIDTH // 4),
                     ("RIGHT: FIRE", 3 * VIRTUAL_WIDTH // 4)):
        hint = small_font.render(label, True, WHITE)
        surface.blit(hint, hint.get_rect(center=(x, VIRTUAL_HEIGHT - 50)))
    if game_over:
        centered_text(surface, font, "GAME OVER", RED, 700)
        for i, value in enumerate(top):
            centered_text(surface, font, f"{i + 1}. {value}", YELLOW, 820 + i * 70)
        centered_text(surface, small_font, "Press SPACE or click/tap to restart", WHITE, 1230)
        if not score_write_ok:
            centered_text(surface, small_font, "High scores could not be saved to disk", RED, 1290)


def main():
    global jump_snd, explode_snd, boss_snd, laser_snd, enemy_snd, score_saved, top, score_write_ok

    # Initialize only required modules; audio failure is handled separately.
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.mixer.init()
    except pygame.error as error:
        print(f"Audio unavailable; continuing without sound: {error}")
    jump_snd = load_sound("jump.wav") or synth_effect(85, 170, 0.25, 0.65, 0.32)
    explode_snd = load_sound("explode.wav") or synth_effect(160, 42, 0.32, 0.83, 0.55)
    boss_snd = load_sound("boss.wav") or synth_effect(460, 105, 0.85, 0.08, 0.34)
    laser_snd = synth_effect(1150, 320, 0.08, 0.03, 0.09)
    enemy_snd = synth_effect(230, 80, 0.22, 0.15, 0.31)

    start_space_theme()
    info = pygame.display.Info()
    scale = max(0.1, min(1.0, (info.current_w - 80) / VIRTUAL_WIDTH,
                         (info.current_h - 100) / VIRTUAL_HEIGHT))
    size = (round(VIRTUAL_WIDTH * scale), round(VIRTUAL_HEIGHT * scale))
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Space Platformer")
    surface = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT))
    font = pygame.font.SysFont(None, 72)
    small_font = pygame.font.SysFont(None, 30)
    clock = pygame.time.Clock()
    star_layers = [
        {"stars": generate_starfield(300), "speed": 0.3, "color": WHITE},
        {"stars": generate_starfield(300), "speed": 0.6, "color": (200, 200, 255)},
        {"stars": generate_starfield(300), "speed": 1.0, "color": YELLOW},
    ]
    reset_game()
    running = True
    held_keys = set()
    fingers = {}  # Keep each thumb on its original control until it lifts.
    tap_thrust = tap_fire = False
    mouse_thrust = mouse_shoot = was_thrusting = False
    accumulator = 0.0
    step = 1.0 / FPS

    while running:
        accumulator += min(clock.tick(FPS) / 1000.0, 0.25)
        for event in pygame.event.get():
            restart = False
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                held_keys.add(event.key)
                if event.key == pygame.K_ESCAPE:
                    running = False
                restart = event.key == pygame.K_SPACE
            elif event.type == pygame.KEYUP:
                held_keys.discard(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and not getattr(event, "touch", False):
                if event.button == 1:
                    mouse_thrust = True
                    restart = True
                elif event.button == 3:
                    mouse_shoot = True
            elif event.type == pygame.MOUSEBUTTONUP and not getattr(event, "touch", False):
                if event.button == 1:
                    mouse_thrust = False
                elif event.button == 3:
                    mouse_shoot = False
            elif event.type == pygame.FINGERDOWN:
                action = "thrust" if event.x < 0.5 else "fire"
                fingers[event.touch_id, event.finger_id] = action
                tap_thrust |= action == "thrust"
                tap_fire |= action == "fire"
                restart = True
            elif event.type == pygame.FINGERUP:
                fingers.pop((event.touch_id, event.finger_id), None)
            elif event.type == pygame.WINDOWFOCUSLOST:
                held_keys.clear()
                fingers.clear()
                tap_thrust = tap_fire = False
                mouse_thrust = mouse_shoot = False
            if game_over and restart:
                reset_game()
                accumulator = 0.0
                was_thrusting = False

        if not running:
            break
        thrusting = mouse_thrust or "thrust" in fingers.values() or pygame.K_SPACE in held_keys
        shooting = mouse_shoot or "fire" in fingers.values() or pygame.K_LSHIFT in held_keys
        if thrusting and not was_thrusting and not game_over:
            play_sound(jump_snd)
        was_thrusting = thrusting
        while accumulator >= step:
            update_game(thrusting or tap_thrust, shooting or tap_fire)
            tap_thrust = tap_fire = False
            accumulator -= step
        if game_over and not score_saved:
            top, score_write_ok = save_highscore(score)
            score_saved = True

        draw_game(surface, font, small_font, star_layers, thrusting)
        shake_x = random.randint(-camera_shake, camera_shake) if camera_shake else 0
        shake_y = random.randint(-camera_shake, camera_shake) if camera_shake else 0
        screen.fill(BLACK)
        scaled = pygame.transform.smoothscale(surface, size)
        screen.blit(scaled, (round(shake_x * scale), round(shake_y * scale)))
        pygame.display.flip()


if __name__ == "__main__":
    try:
        main()
    finally:
        pygame.quit()
