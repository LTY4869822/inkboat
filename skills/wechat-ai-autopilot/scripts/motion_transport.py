"""ID-free transport adapter for the four observed WeChat motion cards.

Preserves approved text, colors, typography, card dimensions and final layout.
It does not modify the immutable workshop revision or remove motion.
"""
from copy import deepcopy
import re
import xml.etree.ElementTree as ET

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
NAMES = {'引文显影': 'quote', '步骤接力': 'steps', '双栏对照': 'comparison', '结论收束': 'conclusion'}
VERSION = 'id-free-four-cards-v1'
TRIGGER = '0s;click;touchstart'

def name(e):
    return e.tag.rsplit('}', 1)[-1]

def node(tag, **attrs):
    return ET.Element('{' + NS + '}' + tag, {k.replace('_', '-'): str(v) for k, v in attrs.items()})

def animation(tag='animate', **attrs):
    return node(tag, begin=TRIGGER, restart='whenNotActive', repeatCount='1', fill='freeze', **attrs)

def hitbox(height):
    return node('rect', x=-1000, y=0, width=2700, height=height, fill='transparent', pointer_events='all')

def remove_animations(e):
    for parent in list(e.iter()):
        for child in list(parent):
            if name(child) in ('animate', 'animateTransform'):
                parent.remove(child)

def convert_svg(raw):
    match = re.search(r'''aria-label=(["'])(.*?)\1''', raw)
    label = match.group(2).split('：')[-1] if match else 'unknown'
    kind = NAMES.get(label)
    if not kind:
        return raw, {'kind': label, 'converted': False, 'reason': 'not covered by the observed adapter'}
    svg = ET.fromstring(raw)
    animations=[e for e in svg.iter() if name(e) in ('animate','animateTransform')]
    if not animations:
        return raw, {'kind': kind, 'converted': False, 'reason': 'static card'}
    if 'url(#' not in raw and not re.search(r'\w+\.click', raw):
        return raw, {'kind': kind, 'converted': False, 'reason': 'already independent of IDs'}
    if any(a.get('repeatCount','1') != '1' for a in animations):
        return raw, {'kind': kind, 'converted': False, 'reason': 'looping variant not verified'}
    if kind == 'steps' and len([e for e in svg if name(e)=='circle' and e.get('r')=='38']) != 3:
        return raw, {'kind': kind, 'converted': False, 'reason': 'only three-node variant verified'}
    before_text = ''.join(svg.itertext())
    height = int(svg.get('viewBox', '0 0 720 450').split()[-1])
    if kind == 'quote':
        # A moving paper veil reveals the original text without url(#clipId).
        for child in list(svg):
            if name(child) == 'defs':
                svg.remove(child)
            child.attrib.pop('clip-path', None)
        veil = node('g', transform='translate(0 0)')
        veil.append(animation('animateTransform', attributeName='transform', type='translate',
                              values='-552 0;0 0;0 0', dur='6s', keyTimes='0;.65;1'))
        veil.append(node('rect', x=654, y=100, width=552, height=170, fill='#f3efe3'))
        veil.append(hitbox(height))
        svg.append(veil)
    elif kind == 'steps':
        # The whole card receives a click. One halo visits the three nodes;
        # the static node labels and final faint rings are always readable.
        root_group = node('g', stroke_dashoffset=0)
        children = list(svg)
        animated_line = next(e for e in children if name(e) == 'path' and e.get('pathLength') == '100')
        line_animation = deepcopy(next(e for e in animated_line if name(e) == 'animate'))
        line_animation.set('begin', TRIGGER)
        line_animation.set('restart', 'whenNotActive')
        remove_animations(svg)
        animated_line.attrib.pop('stroke-dashoffset', None)
        root_group.append(line_animation)
        for child in children:
            svg.remove(child)
            root_group.append(child)
        rings = [e for e in children if name(e) == 'circle' and e.get('r') == '38']
        if len(rings) != 3:
            raise ValueError('This adapter requires the observed three-node steps card')
        positions = [float(e.get('cx')) for e in rings]
        offsets = [p - positions[0] for p in positions]
        halo = node('g', transform='translate(0 0)', opacity=0)
        halo.append(animation('animateTransform', attributeName='transform', type='translate',
                              values=f'0 0;0 0;{offsets[1]:g} 0;{offsets[1]:g} 0;{offsets[2]:g} 0;{offsets[2]:g} 0',
                              dur='8s', keyTimes='0;.16;.29;.46;.59;1'))
        halo.append(animation(attributeName='opacity', values='0;1;1;1;1;0;0', dur='8s', keyTimes='0;.04;.16;.29;.46;.65;1'))
        halo.append(node('circle', cx=positions[0], cy=202, r=38, fill='none', stroke='#e3d7a8'))
        halo.append(hitbox(height))
        root_group.append(halo)
        svg.append(root_group)
    elif kind == 'comparison':
        # Nested groups share bubbled click events. The right group compensates
        # for the outer left translation, so both original trajectories remain.
        groups = [e for e in svg if name(e) == 'g']
        if len(groups) != 2:
            raise ValueError('Unexpected comparison card')
        left, right = groups
        left_anim = next(e for e in left if name(e) == 'animateTransform')
        right_anim = next(e for e in right if name(e) == 'animateTransform')
        right_anim.set('values', '700 0;0 0;0 0')
        for a in (left_anim, right_anim):
            a.set('begin', TRIGGER)
            a.set('restart', 'whenNotActive')
        svg.remove(right)
        right.append(hitbox(height))
        left.append(right)
    elif kind == 'conclusion':
        group = next(e for e in svg if name(e) == 'g')
        a = next(e for e in group if name(e) == 'animate')
        a.set('begin', TRIGGER)
        a.set('restart', 'whenNotActive')
        group.append(hitbox(height))
    for e in svg.iter():
        e.attrib.pop('id', None)
    if ''.join(svg.itertext()) != before_text:
        raise ValueError('Adapter changed approved text')
    result = ET.tostring(svg, encoding='unicode', short_empty_elements=False)
    if 'url(#' in result or re.search(r'\w+\.click', result):
        raise ValueError('Adapter still depends on stripped SVG IDs')
    return result, {'kind': kind, 'converted': True, 'trigger': TRIGGER, 'click_target': 'entire card', 'final_text_preserved': True}

def adapt(document):
    report = []
    def replace(match):
        result, observation = convert_svg(match.group(0))
        report.append(observation)
        return result
    result = re.sub(r'<svg\b[\s\S]*?</svg>', replace, document)
    return result, report

