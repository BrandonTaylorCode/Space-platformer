# Space Platformer 🚀

A Python-based space shooter built with Pygame.

Pilot your spacecraft through an asteroid field, destroy incoming obstacles, fight increasingly powerful bosses, and compete for the highest score.

## Features

- Custom-designed spacecraft and animated asteroid field
- Asteroids that break into smaller fragments
- Higher scores for destroying smaller asteroids
- Progressive boss encounters with health bars
- Enemy projectiles and collision detection
- Particle explosion effects
- Synthesized sound effects and original looping space music
- Desktop keyboard and mouse controls
- Mobile touchscreen controls
- Persistent top-five high-score leaderboard

## Requirements

- Python 3
- Pygame

Install Pygame:

```bash
pip install pygame
```

## How to Run

Download or clone this repository.

Run the game:

```bash
python space_platformer.py
```

## Controls

| Input | Action |
|---|---|
| Space | Thrust |
| Left Shift | Fire |
| Left Mouse Button | Thrust |
| Right Mouse Button | Fire |
| Escape | Exit |
| Touch Left Side | Thrust |
| Touch Right Side | Fire |

After game over, press Space or click/tap to restart.

## Audio

The game generates its own music and sound effects. Optional external sound files can be placed beside the Python file:

- `jump.wav`
- `explode.wav`
- `boss.wav`

The game can continue without these files.

## High Scores

The top five scores are saved locally in `highscores.txt` beside the game file.

## Technology

- Python
- Pygame
- Procedural audio generation
- Object-oriented game concepts and game-loop programming
- Collision detection and physics

---

**Project:** Space Platformer  
**Developer:** Brandon Taylor
