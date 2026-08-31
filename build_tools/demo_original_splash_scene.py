"""Adaptação do motor canônico para o canvas Qt, apenas na demonstração."""
import splash_deep_trust_engine as engine


class OriginalSplashScene:
    def __init__(self):
        engine.pygame.font.init()
        self.surface = engine.pygame.Surface((engine.W, engine.H))
        self.stars = [engine.WarpStar() for _ in range(engine.STAR_COUNT)]
        self.rare = [engine.RareStar() for _ in range(8)]
        self.name_stars = [engine.NameStar(p) for p in engine.build_text_points("NABICODE", 96, 3)]

    def render(self, elapsed, dt):
        # Mesma formação original; somente a saída automática é suspensa
        # enquanto a demonstração aguarda o login.
        fade = engine.smooth(elapsed)
        accel = engine.smooth((elapsed - 2.0) / 3.6)
        decel = engine.smooth((elapsed - 6.35) / 2.35)
        warp = engine.clamp(accel * (1 - decel * 0.88))
        warp *= 1 - 0.46 * engine.smooth((elapsed - 4.55) / 1.45)
        speed = 40 + 540 * warp ** 2.60
        progress = engine.smooth((elapsed - 4.70) / 2.85)
        self.surface.fill(engine.SPACE)
        for star in self.stars:
            star.update_draw(self.surface, dt, elapsed, speed, warp, fade)
        for star in self.rare:
            star.draw(self.surface, elapsed, fade, warp)
        if elapsed > 4.45:
            for star in self.name_stars:
                star.draw(self.surface, progress, elapsed, fade)
        engine.draw_vignette(self.surface)
        if fade < 0.999:
            mask = engine.pygame.Surface((engine.W, engine.H))
            mask.fill((0, 0, 0))
            mask.set_alpha(int(255 * (1 - fade)))
            self.surface.blit(mask, (0, 0))
        return engine.pygame.image.tobytes(self.surface, "RGB")
