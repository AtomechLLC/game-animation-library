// The previews' playback speed control: a labelled select whose choice is remembered across moves, games and visits
// (localStorage "fd-speed"), since full speed on loop is hard to watch. def is the viewer's speed until one is picked.
const KEY = 'fd-speed', SPEEDS = [[1, '1× full'], [0.5, '0.5×'], [0.25, '0.25×'], [0.1, '0.1×']];

export function speedHtml(def) {
  const cur = saved() ?? def;
  return `<label class="v3d-speedl" title="Playback speed"><span aria-hidden="true">⏱</span><span class="v3d-speedt">Speed</span>`
    + `<select class="v3d-speed" aria-label="Playback speed">${SPEEDS.map(([v, l]) => `<option value="${v}"${v === cur ? ' selected' : ''}>${l}</option>`).join('')}</select></label>`;
}

// the speed to start at, and remember each change: onChange gets the new speed
export function bindSpeed(select, def, onChange) {
  select.onchange = () => { const v = +select.value; try { localStorage.setItem(KEY, v) } catch (e) {} onChange(v) };
  return saved() ?? def;
}

function saved() {
  let v = null;
  try { v = +localStorage.getItem(KEY) } catch (e) {}
  return SPEEDS.some(([s]) => s === v) ? v : null;
}
