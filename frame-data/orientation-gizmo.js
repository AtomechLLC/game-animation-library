// Blender-style orientation gizmo (canvas 2D), ported from the centerpiece splat viewer in
// wia-seasonal-ui-asset-generator (three-orientation-gizmo.ts), itself ported from
// https://github.com/joezappie/three-orientation-gizmo (ISC).
//
// Shows the world axes as the camera sees them (from the camera's world rotation, so lookAt cameras work). The bubble
// under the pointer turns white; a click calls onAxisSelected({axis, direction}). Call update() after the camera moves.
import {Matrix4, Vector3} from 'three';

const DEFAULT_OPTIONS = {
  size: 90, padding: 8, bubbleSizePrimary: 8, bubbleSizeSecondary: 6, showSecondary: true, lineWidth: 2,
  fontSize: '11px', fontFamily: 'arial', fontWeight: 'bold', fontColor: '#151515', fontYAdjust: 0,
  colors: {x: ['#f73c3c', '#942424'], y: ['#6ccb26', '#417a17'], z: ['#178cf0', '#0e5490']},
};

export class OrientationGizmo {
  constructor(camera, canvas, options) {
    this.camera = camera;
    this.options = {...DEFAULT_OPTIONS, ...options, colors: {...DEFAULT_OPTIONS.colors, ...options?.colors}};
    this.canvas = canvas;
    this.context = canvas.getContext('2d');
    this.canvas.width = this.canvas.height = this.options.size;
    this.mouse = null; this.selectedAxis = null; this.onAxisSelected = null;
    const o = this.options;
    this.bubbles = [
      {axis: 'x', direction: new Vector3(1, 0, 0), size: o.bubbleSizePrimary, color: o.colors.x, line: o.lineWidth, label: 'X'},
      {axis: 'y', direction: new Vector3(0, 1, 0), size: o.bubbleSizePrimary, color: o.colors.y, line: o.lineWidth, label: 'Y'},
      {axis: 'z', direction: new Vector3(0, 0, 1), size: o.bubbleSizePrimary, color: o.colors.z, line: o.lineWidth, label: 'Z'},
      {axis: '-x', direction: new Vector3(-1, 0, 0), size: o.bubbleSizeSecondary, color: o.colors.x},
      {axis: '-y', direction: new Vector3(0, -1, 0), size: o.bubbleSizeSecondary, color: o.colors.y},
      {axis: '-z', direction: new Vector3(0, 0, -1), size: o.bubbleSizeSecondary, color: o.colors.z},
    ];
    this.center = new Vector3(o.size / 2, o.size / 2, 0);
    this.onMouseMove = e => { const r = this.canvas.getBoundingClientRect(); this.mouse = new Vector3(e.clientX - r.left, e.clientY - r.top, 0) };
    this.onMouseOut = () => { this.mouse = null; this.selectedAxis = null };
    this.onMouseClick = () => {
      if (this.onAxisSelected && this.selectedAxis) this.onAxisSelected({axis: this.selectedAxis.axis, direction: this.selectedAxis.direction.clone()});
    };
    canvas.addEventListener('mousemove', this.onMouseMove);
    canvas.addEventListener('mouseout', this.onMouseOut);
    canvas.addEventListener('click', this.onMouseClick);
  }

  dispose() {
    this.canvas.removeEventListener('mousemove', this.onMouseMove);
    this.canvas.removeEventListener('mouseout', this.onMouseOut);
    this.canvas.removeEventListener('click', this.onMouseClick);
  }

  update() {
    this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.camera.updateMatrixWorld();
    const invRotMat = new Matrix4().extractRotation(this.camera.matrixWorld).invert();
    for (const b of this.bubbles) b.position = this.getBubblePosition(b.direction.clone().applyMatrix4(invRotMat));
    const layers = this.bubbles.filter(b => this.options.showSecondary || !b.axis.startsWith('-'));
    layers.sort((a, b) => a.position.z > b.position.z ? 1 : -1);
    this.selectedAxis = null;
    if (this.mouse) {
      let closest = Infinity;
      for (const b of layers) {
        const d = this.mouse.distanceTo(b.position);
        if (d < b.size && d < closest) { closest = d; this.selectedAxis = b }
      }
    }
    this.drawLayers(layers);
  }

  drawCircle(p, radius, color) {
    const c = this.context;
    c.beginPath(); c.arc(p.x, p.y, radius, 0, 2 * Math.PI, false); c.fillStyle = color; c.fill(); c.closePath();
  }

  drawLine(p1, p2, width, color) {
    const c = this.context;
    c.beginPath(); c.moveTo(p1.x, p1.y); c.lineTo(p2.x, p2.y); c.lineWidth = width; c.strokeStyle = color; c.stroke(); c.closePath();
  }

  drawLayers(layers) {
    const o = this.options, c = this.context;
    for (const b of layers) {
      const color = this.selectedAxis === b ? '#ffffff' : b.position.z >= -0.01 ? b.color[0] : b.color[1];
      this.drawCircle(b.position, b.size, color);
      if (b.line) this.drawLine(this.center, b.position, b.line, color);
      if (b.label) {
        c.font = [o.fontWeight, o.fontSize, o.fontFamily].join(' ');
        c.fillStyle = o.fontColor; c.textBaseline = 'middle'; c.textAlign = 'center';
        c.fillText(b.label, b.position.x, b.position.y + o.fontYAdjust);
      }
    }
  }

  getBubblePosition(p) {
    const radius = this.center.x - this.options.bubbleSizePrimary / 2 - this.options.padding;
    return new Vector3(p.x * radius + this.center.x, this.center.y - p.y * radius, p.z);
  }
}
