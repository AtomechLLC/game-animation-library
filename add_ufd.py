"""Add Super Smash Bros. Ultimate hitbox GIFs from ultimateframedata.com to library.json.

Downloads each mapped move GIF, converts it to a 400px animated WebP at
gifs/<id>-ufd-<n>.webp and appends a `gifs` record to that animation.
Safe to rerun: records already present (same media_url) are skipped.
Needs curl and ffmpeg.
"""
import json, os, subprocess, tempfile

GAME = 'Super Smash Bros. Ultimate'
NAMES = {'link': 'Link', 'marth': 'Marth', 'ike': 'Ike', 'ganondorf': 'Ganondorf', 'ryu': 'Ryu', 'ken': 'Ken',
         'little_mac': 'Little Mac', 'simon': 'Simon', 'bowser': 'Bowser', 'terry': 'Terry', 'cloud': 'Cloud',
         'incineroar': 'Incineroar', 'sephiroth': 'Sephiroth', 'sheik': 'Sheik', 'captain_falcon': 'Captain Falcon',
         'fox': 'Fox', 'sonic': 'Sonic', 'lucina': 'Lucina', 'pit': 'Pit', 'samus': 'Samus', 'snake': 'Snake',
         'pikachu': 'Pikachu', 'zelda': 'Zelda', 'mega_man': 'Mega Man', 'kazuya': 'Kazuya', 'hero': 'Hero',
         'ness': 'Ness', 'bayonetta': 'Bayonetta'}

# animation id -> [(character page, gif name, move label)]
MAP = {
 'melee.light-attack': [('link', 'LinkJab1', 'jab'), ('marth', 'MarthJab1', 'jab')],
 'melee.light-attack-combo-string': [('marth', 'MarthDancingBlade1', 'Dancing Blade hit 1'), ('marth', 'MarthDancingBlade4', 'Dancing Blade hit 4')],
 'melee.heavy-attack': [('ganondorf', 'GanondorfFSmash', 'forward smash'), ('ganondorf', 'GanondorfWarlockPunchG', 'Warlock Punch')],
 'melee.charged-attack': [('ike', 'IkeEruptionMax', 'Eruption, fully charged'), ('marth', 'MarthShieldbreakerMax', 'Shield Breaker, fully charged')],
 'melee.overhead-slam': [('ike', 'IkeFSmash', 'forward smash')],
 'melee.horizontal-sweep': [('ike', 'IkeDSmash', 'down smash'), ('marth', 'MarthDSmash', 'down smash')],
 'melee.thrust-stab': [('marth', 'MarthShieldbreaker', 'Shield Breaker'), ('sephiroth', 'SephirothBladeDash', 'Blade Dash')],
 'melee.spin-attack': [('link', 'LinkSpinAttackG', 'Spin Attack'), ('bowser', 'BowserWhirlingFortressG', 'Whirling Fortress')],
 'melee.uppercut-launcher': [('ryu', 'RyuUTiltHeavy', 'heavy up tilt'), ('terry', 'TerryUTilt', 'up tilt')],
 'melee.aerial-attack': [('marth', 'MarthFAir', 'forward air'), ('cloud', 'CloudFAir', 'forward air')],
 'melee.plunging-downward-attack': [('link', 'LinkDAir', 'down air'), ('sheik', 'SheikDAir', 'down air')],
 'melee.jump-attack': [('ike', 'IkeAetherG', 'Aether'), ('terry', 'TerryPowerDunkStrong', 'Power Dunk')],
 'melee.dash-attack-lunge': [('marth', 'MarthDashAttack', 'dash attack'), ('ike', 'IkeDashAttack', 'dash attack')],
 'melee.combo-finisher': [('link', 'LinkJab3', 'jab finisher'), ('cloud', 'CloudJab3', 'jab finisher')],
 'melee.kick': [('ken', 'KenOosotoMawashiGeri', 'Oosoto Mawashi Geri roundhouse'), ('ken', 'KenFTiltHeavy', 'heavy forward tilt')],
 'melee.punch-combo': [('little_mac', 'LittleMacJab1', 'jab 1'), ('little_mac', 'LittleMacJab3', 'jab 3')],
 'melee.grab-throw': [('incineroar', 'IncineroarFThrow', 'forward throw'), ('ganondorf', 'GanondorfBThrow', 'back throw')],
 'melee.ground-pound': [('bowser', 'BowserBowserBombG', 'Bowser Bomb')],
 'melee.weapon-art-skill-attack': [('sephiroth', 'SephirothOctaslash', 'Octaslash'), ('cloud', 'CloudFinishingTouchG', 'Finishing Touch')],
 'melee.iaido-quick-draw-slash': [('ike', 'IkeQuickDraw', 'Quick Draw')],
 'melee.whip-chain-lash': [('simon', 'SimonFSmash', 'forward smash'), ('simon', 'SimonFTilt', 'forward tilt')],
 'defense.counter-attack': [('marth', 'MarthCounterHit', 'Counter'), ('little_mac', 'LittleMacSlipCounterHitG', 'Slip Counter')],
 'reactions.get-up-wake-up': [('ryu', 'ryuGetupAttackU', 'get-up attack'), ('link', 'linkGetupAttackU', 'get-up attack')],
 'fighting.special-move-projectile': [('ryu', 'RyuHadokenHeavy', 'Hadoken'), ('terry', 'TerryPowerWaveGStrong', 'Power Wave')],
 'fighting.rising-uppercut-shoryuken': [('ryu', 'RyuShoryukenHeavy', 'Shoryuken'), ('ken', 'KenShoryukenHeavy', 'Shoryuken')],
 'fighting.spinning-kick-tatsumaki': [('ryu', 'RyuTatsumakiSenpukyakuHeavyGrounded', 'Tatsumaki Senpukyaku'), ('ken', 'KenTatsumakiSenpukyakuStrongGrounded', 'Tatsumaki Senpukyaku')],
 'fighting.command-grab': [('ganondorf', 'GanondorfFlameChokeG', 'Flame Choke'), ('incineroar', 'IncineroarAlolanWhipG', 'Alolan Whip')],
 'fighting.super-critical-art': [('terry', 'TerryPowerGeyser', 'Power Geyser'), ('terry', 'TerryBusterWolf', 'Buster Wolf')],
 'melee.sprint-attack': [('captain_falcon', 'CaptainFalconDashAttack', 'dash attack'), ('fox', 'FoxDashAttack', 'dash attack')],
 'melee.rolling-attack': [('sonic', 'SonicSpinDashAerial', 'Spin Dash')],
 'melee.riposte': [('ike', 'IkeCounterHit', 'Counter, counterattack'), ('lucina', 'LucinaCounterHit', 'Counter, counterattack')],
 'melee.dual-wield-flurry': [('pit', 'PitJabRapid', 'rapid jab with twin blades')],
 'ranged.charge-shot': [('samus', 'SamusChargeShotMax', 'Charge Shot, fully charged')],
 'magic.lightning-strike': [('pikachu', 'PikachuThunder', 'Thunder')],
 'magic.teleport-blink': [('zelda', 'ZeldaFaroresWindG', "Farore's Wind"), ('sheik', 'SheikVanishG', 'Vanish')],
 'magic.shield-barrier': [('fox', 'FoxReflector', 'Reflector'), ('mega_man', 'MegaManLeafShield', 'Leaf Shield')],
 'magic.beam-attack': [('kazuya', 'Shoto4DevilBlasterG', 'Devil Blaster')],
 'magic.projectile-cast-fireball': [('ness', 'NessPKFireG', 'PK Fire')],
 'magic.spell-cast-instant': [('hero', 'Sizzle', 'Sizzle')],
 'defense.perfect-dodge-witch-time': [('bayonetta', 'BayonettaWitchTime', 'Witch Time')],
 'fighting.drive-impact-armor-attack': [('ryu', 'RyuFocusAttackLvl3', 'Focus Attack level 3'), ('ken', 'KenFocusAttackLv3', 'Focus Attack level 3')],
}

# animation id -> [(frame data move id, clip index)]: picked from the moves' hitbox clips in
# frame-data/super-smash-bros-ultimate.json (run tools/frame_data/import_ufd_ssbu.py first), keeping clips where
# the character reads clearly at 400px (wide projectile shots and hitbox-only clips were left out)
MOVES = {
 'magic.charge-up-ki-charge': [('ridley.special.neutral-b-plasma-breath', 1)],
 'cartoon.limited-animation-on-twos': [('mr-game-and-watch.special.side-b-judge', 8)],
 'defense.perfect-dodge-witch-time': [('lucario.special.down-b-double-team', 0)],
 'ranged.grenade-throw': [('king-dedede.special.side-b-gordo-throw', 0)],
 'melee.backstab': [('meta-knight.special.dimensional-cape-attack', 4)],
 'melee.finisher-execution': [('kazuya.special.rage-drive-input-f-d-df-hold-a-b-623-hold-a-b', 0), ('incineroar.special.alolan-whip-lariat-attack', 0)],
 'melee.weapon-art-skill-attack': [('hero.special.flame-slash', 0), ('cloud.special.limit-cross-slash', 1)],
 'melee.charged-attack': [('king-dedede.special.down-b-full-charge-jet-hammer-full-charge', 0)],
 'melee.overhead-slam': [('kirby.special.hammer-full-charge', 0)],
 'melee.whip-chain-lash': [('zero-suit-samus.special.side-b-plasma-whip', 0)],
 'melee.grab-throw': [('snake.grab.forward-throw', 0)],
 'magic.spell-cast-instant': [('hero.special.side-b-zap-zapple-kazap', 3)],
 'magic.area-of-effect-slam': [('donkey-kong.special.down-b-hand-slap', 0)],
 'magic.teleport-blink': [('meta-knight.special.dimensional-cape-attack', 3)],
 'magic.ice-frost-spell': [('ice-climbers.special.down-b-blizzard', 0)],
 'magic.fire-breath-flame-spray': [('ridley.special.neutral-b-plasma-breath', 0), ('piranha-plant.special.side-b-full-charge-poison-breath-full-charge', 0)],
 'magic.telekinesis-force-push': [('rosalina-and-luma.special.down-b-gravitational-pull', 0), ('mewtwo.special.side-b-confusion', 0), ('lucario.special.side-b-force-palm', 0), ('ness.special.down-b-psi-magnet', 0)],
 'magic.shield-barrier': [('wolf.special.down-b-reflector', 1), ('joker.special.arsene-makarakarn-reflect', 0)],
 'defense.parry': [('roy.special.down-b-counter', 0), ('little-mac.special.down-b-slip-counter', 0)],
 'defense.perfect-block-deflect': [('dr-mario.special.side-b-super-sheet', 0), ('mario.special.side-b-cape', 0), ('palutena.special.counter-attack-reflect', 0), ('falco.special.down-b-reflector', 0)],
 'defense.counter-attack': [('sora.special.down-b-counterattack-success', 0), ('corrin.special.counter-surge-attack', 0), ('king-k-rool.special.gut-check-counterattack', 0)],
 'defense.guard-break-shield-break': [('marth.special.neutral-b-shield-breaker', 3), ('lucina.special.neutral-b-shieldbreaker', 3)],
 'defense.air-dash': [('pikachu.special.up-b-quick-attack', 0)],
 'defense.backstep-backflip': [('sheik.special.down-b-bouncing-fish', 0)],
 'fighting.taunt': [('luigi.ground.down-taunt', 0), ('greninja.ground.down-taunt', 0), ('kazuya.ground.demon-s-wrath-side-taunt', 0)],
 'fighting.command-grab': [('ridley.special.side-b-space-pirate-rush-success', 0), ('bowser.special.side-b-flying-slam', 0), ('mii-brawler.special.counter-throw-activated', 0)],
 'fighting.super-critical-art': [('kazuya.special.rage-drive-input-f-d-df-hold-a-b-623-hold-a-b', 2)],
 'enemies.charging-rush': [('pt-charizard.special.side-b-flare-blitz', 0), ('ridley.special.side-b-space-pirate-rush', 0), ('bowser-jr.special.side-b-clown-kart-dash', 0)],
 'enemies.monster-grab-pin': [('ridley.special.side-b-space-pirate-rush-success', 1), ('incineroar.special.side-b-alolan-whip-grab', 0)],
 'exploration.glide-paraglider': [('steve.special.up-b-elytra', 0)],
 'exploration.drive-steer-vehicle': [('wario.special.side-b-wario-bike', 0)],
 'stealth.chokehold-sleeper-hold': [('snake.grab.pummel', 0)],
 'interaction.fishing-cast-reel': [('isabelle.grab.grab', 0)],
 'interaction.plant-water-crops': [('villager.special.timber-tree-grow-fall', 0)],
 'interaction.mine-chop': [('villager.special.timber-axe', 0)],
 'interaction.cook': [('mr-game-and-watch.special.neutral-b-chef', 0)],
 'interaction.eat-drink': [('king-dedede.special.neutral-b-inhale', 1)],
 'sports.swing-golf-tennis-bat': [('ness.ground.forward-smash', 0), ('peach.ground.forward-smash', 1), ('daisy.ground.forward-smash', 2)],
 'creature.dragon-flight-breath': [('ridley.special.up-b-wing-blitz', 0)],
}


def webp(url, out):
    with tempfile.NamedTemporaryFile(suffix='.gif') as t:
        subprocess.run(['curl', '-sSfL', '-m', '60', '-o', t.name, url.replace(' ', '%20')], check=True)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', t.name, '-vf', 'scale=400:-1:flags=lanczos',
                        '-loop', '0', '-c:v', 'libwebp', '-quality', '60', '-compression_level', '6', out], check=True)


d = json.load(open('library.json'))
byid = {a['id']: a for a in d['animations']}
added = 0
for aid, moves in MAP.items():
    a = byid[aid]
    a.setdefault('gifs', [])
    have = {g.get('media_url') for g in a['gifs']}
    n = sum(1 for g in a['gifs'] if g.get('host') == 'Ultimate Frame Data')
    for char, gif, move in moves:
        url = f'https://ultimateframedata.com/hitboxes/{char}/{gif}.gif'
        if url in have:
            continue
        local = f'gifs/{aid}-ufd-{n}.webp'
        try:
            webp(url, local)
        except subprocess.CalledProcessError as e:
            print('failed', url, e)
            continue
        a['gifs'].append({'page_url': f'https://ultimateframedata.com/{char}', 'media_url': url,
                          'title': f'{NAMES[char]} {move}, with hitboxes', 'game': GAME,
                          'host': 'Ultimate Frame Data', 'local': local, 'source_url': url})
        n += 1
        added += 1
fd = json.load(open('frame-data/super-smash-bros-ultimate.json', encoding='utf-8'))
fmoves = {m['id']: m for m in fd['moves']}
cname = {c['id']: c['name'] for c in fd['classes']}
for aid, picks in MOVES.items():
    a = byid[aid]
    a.setdefault('gifs', [])
    have = {g.get('media_url') for g in a['gifs']}
    n = sum(1 for g in a['gifs'] if g.get('host') == 'Ultimate Frame Data')
    for mid, i in picks:
        m = fmoves[mid]
        clip = m['clips'][i]
        url = clip['source']
        if url in have:
            continue
        local = f'gifs/{aid}-ufd-{n}.webp'
        try:
            webp(url, local)
        except subprocess.CalledProcessError as e:
            print('failed', url, e)
            continue
        label = m['name'] + (f' ({clip["label"]})' if len(m['clips']) > 1 else '')
        a['gifs'].append({'page_url': m['url'], 'media_url': url, 'title': f'{cname[m["class"]]} {label}, with hitboxes',
                          'game': GAME, 'host': 'Ultimate Frame Data', 'local': local, 'source_url': url})
        n += 1
        added += 1
json.dump(d, open('library.json', 'w'), indent=1, ensure_ascii=False)
print('added', added)
