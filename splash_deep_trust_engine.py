import math
import random
import sys
import time

try:
    import pygame
except ImportError:
    print("ERRO: pygame/pygame-ce nao encontrado.")
    print("Instale com: python -m pip install pygame-ce")
    sys.exit(1)

# ============================================================
# NabiCode Splash — "Lightspeed"
#
# Conceito:
# - começa com campo estelar profundo
# - acelera brutalmente
# - estrelas viram riscos longos de luz
# - corredor central / efeito hiperespaço
# - branco neon domina; algumas faixas ciano, verde, azul e violeta
# - no auge da velocidade, estrelas brancas são "travadas" no centro
#   e formam NABICODE
# - ao formar o nome, o universo desacelera
# - sem barra, HUD ou segundo texto
# - duração aproximada: 12 s
# ============================================================

W, H = 1280, 720
FPS = 60
DURATION = 12.2
SPACE = (0, 1, 5)

STAR_COUNT = 2050
NAME_STAR_COUNT = 1500

def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))

def smooth(t):
    t = clamp(t)
    return t*t*(3-2*t)

def ease_out(t):
    t = clamp(t)
    return 1-(1-t)**3

def lerp(a,b,t):
    return a+(b-a)*t

PALETTE = [
    ((255,255,255),0.70),
    ((225,245,255),0.11),
    ((110,255,240),0.055),
    ((90,255,150),0.04),
    ((105,165,255),0.035),
    ((195,125,255),0.025),
    ((255,225,135),0.02),
    ((255,130,115),0.015),
]

def choose_color(white_only=False):
    if white_only:
        return random.choice([
            (255,255,255),
            (248,252,255),
            (238,247,255),
            (230,243,255),
        ])
    r=random.random()
    acc=0
    for c,w in PALETTE:
        acc+=w
        if r<=acc:
            return c
    return (255,255,255)

def build_text_points(text="NABICODE",font_size=96,step=3):
    font=pygame.font.SysFont("segoeui",font_size,bold=True)
    surf=font.render(text,True,(255,255,255))
    mask=pygame.mask.from_surface(surf)
    mw,mh=mask.get_size()

    pts=[]
    for y in range(0,mh,step):
        for x in range(0,mw,step):
            if mask.get_at((x,y)):
                pts.append((x-mw/2,y-mh/2))

    random.shuffle(pts)
    if len(pts)>NAME_STAR_COUNT:
        pts=random.sample(pts,NAME_STAR_COUNT)
    return pts


class WarpStar:
    def __init__(self):
        self.reset(True)

    def reset(self,initial=False):
        # ponto 3D centrado no observador
        self.x=random.uniform(-W,W)
        self.y=random.uniform(-H,H)
        self.z=random.uniform(60,W) if initial else W
        self.pz=self.z
        self.color=choose_color(False)
        self.brightness=random.uniform(0.52,1.0)
        self.phase=random.uniform(0,math.tau)
        self.twinkle_speed=random.uniform(0.8,2.3)

    def project(self,z):
        z=max(1,z)
        return (
            (self.x/z)*W + W/2,
            (self.y/z)*H + H/2
        )

    def update_draw(self,screen,dt,now,speed,warp,fade):
        self.pz=self.z
        self.z-=speed*dt

        if self.z<1:
            self.reset(False)

        sx,sy=self.project(self.z)
        px,py=self.project(self.pz)

        if sx<-120 or sx>W+120 or sy<-120 or sy>H+120:
            self.reset(False)
            return

        depth=clamp(1-self.z/W)
        tw=0.76+0.24*math.sin(now*self.twinkle_speed+self.phase)

        power=clamp((0.18+depth*1.2)*self.brightness*tw*fade)
        br,bg,bb=self.color
        color=(int(br*power),int(bg*power),int(bb*power))

        # Em warp alto, o rastro fica muito maior.
        if warp>0.08:
            # No começo da aceleração, mantém boa parte das estrelas como pontos.
            # Conforme o warp cresce, a proporção de riscos aumenta.
            line_probability = 0.10 * clamp((warp - 0.26) / 0.72)

            # estrelas mais próximas têm prioridade para virar risco
            line_probability *= 0.55 + 0.45*depth

            deterministic = (
                (int(abs(self.x)*0.17 + abs(self.y)*0.11 + self.phase*97) % 1000)
                / 1000.0
            )

            if deterministic < line_probability:
                dx=sx-px
                dy=sy-py

                # comprimento cresce progressivamente, sem "encher" a tela cedo demais
                factor=1 + (warp**1.65)*2.85
                tx=sx-dx*factor
                ty=sy-dy*factor

                width=1
                if depth>0.88 and warp>0.70:
                    width=2
                if depth>0.985 and self.brightness>0.94 and warp>0.94:
                    width=3

                pygame.draw.line(
                    screen,
                    color,
                    (int(tx),int(ty)),
                    (int(sx),int(sy)),
                    width
                )

                if depth>0.87 and self.brightness>0.84:
                    pygame.draw.circle(
                        screen,
                        (min(255,int(color[0]*1.16)),
                         min(255,int(color[1]*1.16)),
                         min(255,int(color[2]*1.16))),
                        (int(sx),int(sy)),
                        2
                    )
            else:
                radius=1
                if depth>0.72:
                    radius=2
                pygame.draw.circle(screen,color,(int(sx),int(sy)),radius)
        else:
            radius=1 if depth<0.72 else 2
            pygame.draw.circle(screen,color,(int(sx),int(sy)),radius)


class NameStar:
    def __init__(self,target):
        self.target=target
        self.color=choose_color(True)

        # As estrelas que formarão o nome nascem no espaço profundo,
        # próximas ao ponto de fuga central. Elas começam minúsculas,
        # quase indistinguíveis das estrelas distantes, avançam na direção
        # da câmera e só depois se separam para formar NABICODE.
        angle=random.uniform(0,math.tau)

        # Origem extremamente concentrada no centro.
        radius=random.uniform(2,42)
        self.sx=W/2+math.cos(angle)*radius
        self.sy=H/2+math.sin(angle)*radius*0.55

        self.delay=random.uniform(0,0.72)
        self.curve=random.uniform(-0.38,0.38)
        self.phase=random.uniform(0,math.tau)

        # Profundidade visual: no começo quase não aparece.
        self.depth_seed=random.uniform(0.45,1.0)

    def draw(self,screen,progress,now,fade):
        local=clamp((progress-self.delay*0.6)/max(0.01,1-self.delay*0.6))
        if local<=0:
            return

        p=smooth(local)

        # Ainda muito fundo: não mostrar o aglomerado central.
        if p < 0.16:
            return

        tx=W/2+self.target[0]
        ty=H/2+self.target[1]

        dx=tx-self.sx
        dy=ty-self.sy
        length=math.hypot(dx,dy) or 1
        nx=-dy/length
        ny=dx/length

        # Saída do espaço profundo:
        # primeiros instantes permanecem junto ao ponto de fuga,
        # depois a estrela acelera suavemente até seu ponto na letra.
        # Curva contínua e mais macia para reduzir sensação de travamento.
        travel = 1.0 - (1.0 - p)**2.25
        travel = clamp(travel)

        # Curvatura ainda menor e amortecida.
        arc = math.sin(travel*math.pi) * (10*(1-travel*0.72)) * self.curve

        x=lerp(self.sx,tx,travel)+nx*arc
        y=lerp(self.sy,ty,travel)+ny*arc

        # rastro de luz da própria estrela do nome
        prev = clamp(p-0.014,0,1)
        prev_travel = 1.0 - (1.0 - prev)**2.25
        prev_travel = clamp(prev_travel)
        parc = math.sin(prev_travel*math.pi) * (10*(1-prev_travel*0.72)) * self.curve
        px = lerp(self.sx,tx,prev_travel) + nx*parc
        py = lerp(self.sy,ty,prev_travel) + ny*parc

        br,bg,bb=self.color
        travel_bright=0.62+0.38*p
        travel_col=(
            int(br*travel_bright),
            int(bg*travel_bright),
            int(bb*travel_bright)
        )

        # Rastro curto apenas perto do encaixe para não sujar a tela.
        if 0.82 < p < 0.90:
            pygame.draw.line(
                screen,
                travel_col,
                (int(px),int(py)),
                (int(x),int(y)),
                1
            )

        assembled=smooth((p-0.78)/0.22)
        pulse=0.88+0.12*math.sin(now*1.9+self.phase)

        sweep_x=((now*245)%620)+(W/2-310)
        sweep=clamp(1-abs(tx-sweep_x)/78)

        # Formação imperceptível:
        # enquanto as estrelas ainda estão comprimidas no ponto de fuga,
        # praticamente não são desenhadas. Elas ganham luminosidade apenas
        # quando já começaram a ocupar a forma das letras.
        reveal = smooth((p - 0.22) / 0.48)
        depth_light = (0.025 + 0.975*ease_out(p)) * reveal
        depth_light *= self.depth_seed

        c=(
            min(255,int(lerp(br,255,assembled*0.98)*pulse*depth_light*(1+0.22*sweep*assembled))),
            min(255,int(lerp(bg,255,assembled*0.98)*pulse*depth_light*(1+0.22*sweep*assembled))),
            min(255,int(lerp(bb,255,assembled*0.99)*pulse*depth_light*(1+0.22*sweep*assembled))),
        )

        # No fundo é praticamente um ponto; cresce só próximo da palavra.
        r=1
        if p>0.68:
            r=2
        if assembled>0.94 and sweep>0.65:
            r=3

        pygame.draw.circle(screen,c,(int(x),int(y)),r)

        if assembled>0.32:
            gs=10 if r<3 else 14
            glow=pygame.Surface((gs,gs),pygame.SRCALPHA)
            pygame.draw.circle(
                glow,
                (240,255,253,int((13+31*sweep)*assembled*fade)),
                (gs//2,gs//2),
                gs//2-1
            )
            screen.blit(glow,(int(x)-gs//2,int(y)-gs//2))


class RareStar:
    def __init__(self):
        self.x=random.randint(70,W-70)
        self.y=random.randint(50,H-50)
        self.phase=random.uniform(0,math.tau)
        self.speed=random.uniform(0.45,0.9)
        self.size=random.randint(8,14)
        self.color=random.choice([
            (255,255,255),
            (170,230,255),
            (120,255,225),
            (185,145,255),
        ])

    def draw(self,screen,now,fade,warp):
        # durante o warp máximo desaparece para não poluir
        quiet=1-clamp((warp-0.35)/0.5)
        pulse=max(0,math.sin(now*self.speed+self.phase))**7
        pulse*=quiet
        if pulse<0.025:
            return

        layer=pygame.Surface((W,H),pygame.SRCALPHA)
        a=int(145*pulse*fade)
        r=int(self.size*(0.8+0.45*pulse))

        pygame.draw.circle(layer,(*self.color,min(255,a+70)),(self.x,self.y),2)

        gs=max(12,r*3)
        glow=pygame.Surface((gs,gs),pygame.SRCALPHA)
        gc=gs//2
        pygame.draw.circle(glow,(*self.color,int(a*0.10)),(gc,gc),gs//2-1)
        pygame.draw.circle(glow,(*self.color,int(a*0.22)),(gc,gc),max(2,gs//4))
        layer.blit(glow,(self.x-gc,self.y-gc))

        ray=max(2,int(r*0.38))
        pygame.draw.line(layer,(*self.color,int(a*0.42)),
                         (self.x-ray,self.y),(self.x+ray,self.y),1)
        pygame.draw.line(layer,(*self.color,int(a*0.28)),
                         (self.x,self.y-ray),(self.x,self.y+ray),1)

        screen.blit(layer,(0,0))


def draw_center_bloom(screen,warp,elapsed,fade):
    if warp<0.35:
        return

    strength=smooth((warp-0.35)/0.65)
    pulse=0.85+0.15*math.sin(elapsed*4.0)

    layer=pygame.Surface((W,H),pygame.SRCALPHA)

    for i in range(7):
        r=int(5+i*7+strength*10)
        a=int((50-i*6)*strength*pulse*fade)
        pygame.draw.circle(
            layer,
            (225,255,250,max(0,a)),
            (W//2,H//2),
            r
        )

    # flare horizontal curto e forte no auge
    if strength>0.7:
        a=int(100*(strength-0.7)/0.3*fade)
        pygame.draw.line(
            layer,
            (220,255,250,a),
            (W//2-90,H//2),
            (W//2+90,H//2),
            1
        )

    screen.blit(layer,(0,0))


def draw_vignette(screen):
    layer=pygame.Surface((W,H),pygame.SRCALPHA)
    for i in range(32):
        a=1+i
        pygame.draw.rect(
            layer,
            (0,0,0,a),
            pygame.Rect(i*6,i*4,W-i*12,H-i*8),
            1
        )
    screen.blit(layer,(0,0))


def main():
    pygame.init()
    pygame.display.set_caption("NabiCode — Deep Trust Fluid")

    screen=pygame.display.set_mode((W,H))
    clock=pygame.time.Clock()

    stars=[WarpStar() for _ in range(STAR_COUNT)]
    rare=[RareStar() for _ in range(8)]

    points=build_text_points("NABICODE",96,3)
    name_stars=[NameStar(p) for p in points]

    start=time.perf_counter()
    running=True

    while running:
        dt=clock.tick(FPS)/1000
        elapsed=time.perf_counter()-start

        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                running=False
            elif event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE:
                running=False

        fade_in=smooth(elapsed/1.0)
        fade_out=1-smooth((elapsed-11.0)/1.2)
        fade=fade_in*fade_out

        # timeline
        # 0-2s: espaço normal
        # 2-4.5s: aceleração até hiperespaço
        # 4.5-6.5s: velocidade máxima
        # 5.2-8.2s: estrelas brancas começam a formar NABICODE
        # 7.2-9.5s: universo desacelera
        accel=smooth((elapsed-2.0)/3.6)
        decel=smooth((elapsed-6.35)/2.35)
        warp=clamp(accel*(1-decel*0.88))

        # Quando o nome começa a nascer, o fundo perde agressividade
        # para a formação parecer limpa e confiável.
        name_cleanup = smooth((elapsed-4.55)/1.45)
        warp *= (1.0 - 0.46*name_cleanup)

        # velocidade extrema
        speed=40 + 540*(warp**2.60)

        name_progress=smooth((elapsed-4.70)/2.85)

        screen.fill(SPACE)

        for s in stars:
            s.update_draw(screen,dt,elapsed,speed,warp,fade)


        # estrelas raras permanecem no fundo, mas somem no auge do warp
        for rs in rare:
            rs.draw(screen,elapsed,fade,warp)

        # no auge, as estrelas brancas se desprendem do túnel e formam o nome
        if elapsed>4.45:
            for ns in name_stars:
                ns.draw(screen,name_progress,elapsed,fade)

        draw_vignette(screen)

        if fade<0.999:
            mask=pygame.Surface((W,H))
            mask.fill((0,0,0))
            mask.set_alpha(int(255*(1-fade)))
            screen.blit(mask,(0,0))

        pygame.display.flip()

        if elapsed>=DURATION:
            running=False

    pygame.quit()


if __name__=="__main__":
    main()
