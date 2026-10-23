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


def webp(url, out):
    with tempfile.NamedTemporaryFile(suffix='.gif') as t:
        subprocess.run(['curl', '-sSfL', '-m', '60', '-o', t.name, url], check=True)
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
json.dump(d, open('library.json', 'w'), indent=1, ensure_ascii=False)
print('added', added)
