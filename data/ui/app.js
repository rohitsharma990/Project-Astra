import * as THREE from './vendor/three.module.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';

window.astraScriptStarted = true;
const canvas = document.querySelector('#scene');
const container = document.querySelector('#stage');
const loading = document.querySelector('#loading');
const status = document.querySelector('#status');
const chat = document.querySelector('#chat');
const menu = document.querySelector('#menu');
const approval = document.querySelector('#approval');
const messages = document.querySelector('#messages');
let backend;
let host;
let model;
let mixer;
let animationController;
let clock = new THREE.Clock();
let pointer = new THREE.Vector2();
let dragging = false;
let activePointerId = null;
let dragStartScreen = { x: 0, y: 0 };
let dragWindowOrigin = { x: 80, y: 120 };
let dragPositionReady = false;
let latestScreen = { x: 0, y: 0 };
let scale = 1;
let settings = { x: 80, y: 120, width: 360, height: 520, scale: 1, always_on_top: true, edge_behavior: false };
window.DEBUG_UI = false;
const DEBUG_ANIMATION = window.DEBUG_UI === true;
window.astraModelLoaded = false;

function logUi(message, ...args) {
  if (window.DEBUG_UI) console.info(`[UI] ${message}`, ...args);
}
window.addEventListener('error', event => {
  const detail = `Page error: ${event.message} (${event.filename || 'unknown'}:${event.lineno || 0})`;
  console.error(detail);
  status.textContent = detail;
  status.classList.remove('hidden');
});
window.addEventListener('unhandledrejection', event => {
  const detail = `Page error: ${event.reason?.message || event.reason}`;
  console.error(detail);
  status.textContent = detail;
  status.classList.remove('hidden');
});

new QWebChannel(qt.webChannelTransport, channel => { backend = channel.objects.backend; host = channel.objects.host; });
window.astraSettings = value => {
  settings = { ...settings, ...value };
  scale = Number(settings.scale) || 1;
  frameModel();
};
window.__astraPending.settings.splice(0).forEach(window.astraSettings);

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(28, innerWidth / innerHeight, .01, 100);
camera.position.set(0, 1.05, 4.2);
scene.add(new THREE.HemisphereLight(0xd9fff0, 0x18201f, 2.2));
const key = new THREE.DirectionalLight(0xffd2ba, 2.3); key.position.set(-2, 3, 4); scene.add(key);

function resize() {
  const width = Math.max(container.clientWidth, 1);
  const height = Math.max(container.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  frameModel();
}
addEventListener('resize', resize); resize();

function canvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width - .5) * 1.1,
    y: -((event.clientY - rect.top) / rect.height - .5) * .9,
  };
}

const EXPECTED_CLIP_NAMES = ['Idle', 'Talking', 'Happy', 'Reacting', 'Waving', 'Sitting', 'Thankful'];
const EXACT_CLIP_MAP = Object.freeze({
  idle: 'Idle',
  speaking: 'Talking',
  happy: 'Happy',
  successful: 'Happy',
  success: 'Happy',
  greeting: 'Waving',
  wave: 'Waving',
  waving: 'Waving',
  reaction: 'Reacting',
  reacting: 'Reacting',
  thankful: 'Thankful',
  sitting: 'Sitting',
});

class AnimationController {
  constructor(root, clips) {
    this.root = root;
    this.mixer = clips && clips.length ? new THREE.AnimationMixer(root) : null;
    this.actions = new Map();
    this.state = 'idle';
    this.currentAction = null;
    this.currentActionName = null;
    this.dragging = false;
    this.dragTarget = new THREE.Vector3();
    this.dragPosition = new THREE.Vector3();
    this.dragVelocity = new THREE.Vector3();
    this.dropStarted = 0;
    this.basePosition = root.position.clone();
    this.baseRotation = root.rotation.clone();
    this.mouth = null;
    this.mouthScale = new THREE.Vector3();
    this.mouthPosition = new THREE.Vector3();
    this.mouthOpen = 0;
    this.mouthTarget = 0;
    this.nextMouthPulse = 0;
    this.fadeDuration = 0.25;
    this.priority = {
      dragging: 100,
      speaking: 90,
      listening: 80,
      thinking: 70,
      approval: 60,
      happy: 55,
      success: 55,
      error: 40,
      idle: 10,
      dropping: 75,
    };
    this.oneShotStates = new Set(['happy', 'reacting', 'waving', 'thankful']);

    if (this.mixer) {
      clips.forEach(clip => {
        const clipName = String(clip.name || '').trim();
        if (!clipName) return;
        const action = this.mixer.clipAction(clip);
        action.setLoop(clipName === 'Idle' || clipName === 'Talking' || clipName === 'Sitting' ? THREE.LoopRepeat : THREE.LoopOnce, clipName === 'Idle' || clipName === 'Talking' || clipName === 'Sitting' ? Infinity : 1);
        if (clipName === 'Idle' || clipName === 'Talking' || clipName === 'Sitting') {
          action.loop = THREE.LoopRepeat;
        } else {
          action.loop = THREE.LoopOnce;
          action.clampWhenFinished = true;
        }
        this.actions.set(clipName, action);
      });

      this.mixer.addEventListener('finished', event => {
        const actionName = this.findActionName(event.action);
        if (!actionName) return;
        const logicalName = this.toLogicalState(actionName);
        if (!this.oneShotStates.has(logicalName)) return;
        if (this.state !== logicalName) return;
        if (DEBUG_ANIMATION) console.debug('[ANIMATION] finished -> idle');
        this.setState('idle');
      });
    }

    root.traverse(node => {
      const nodeName = (node.name || '').toLowerCase();
      if (node.isMesh && /mouth|jaw|lips/.test(nodeName) && !this.mouth) {
        this.mouth = node;
      }
    });
    if (this.mouth) {
      this.mouthScale.copy(this.mouth.scale);
      this.mouthPosition.copy(this.mouth.position);
    }

    if (DEBUG_ANIMATION && this.mixer) {
      const details = clips.map((clip, index) => `${index + 1}. ${clip.name} (${clip.duration.toFixed(3)}s, ${clip.tracks.length} tracks)`).join('\n');
      console.debug('[ANIMATION] available clips:\n' + details);
    }
  }

  findActionName(action) {
    for (const [name, candidate] of this.actions.entries()) {
      if (candidate === action) return name;
    }
    return null;
  }

  toLogicalState(state) {
    const requestedState = String(state || 'idle').toLowerCase().replace('waiting_for_approval', 'approval').replace('approval_required', 'approval');
    if (requestedState === 'success' || requestedState === 'successful') return 'happy';
    if (requestedState === 'speaking') return 'talking';
    if (requestedState === 'happy') return 'happy';
    if (requestedState === 'greeting' || requestedState === 'wave') return 'waving';
    if (requestedState === 'reaction' || requestedState === 'reacting') return 'reacting';
    if (requestedState === 'thankful') return 'thankful';
    if (requestedState === 'sitting') return 'sitting';
    if (requestedState === 'idle') return 'idle';
    if (requestedState === 'approval' || requestedState === 'thinking' || requestedState === 'listening' || requestedState === 'error') return 'idle';
    return requestedState;
  }

  stateToClipName(state) {
    const requestedState = String(state || 'idle').toLowerCase().replace('waiting_for_approval', 'approval').replace('approval_required', 'approval');
    const clipName = EXACT_CLIP_MAP[requestedState] || EXACT_CLIP_MAP.idle;
    if (clipName === EXACT_CLIP_MAP.idle && requestedState !== 'idle' && requestedState !== 'approval' && requestedState !== 'thinking' && requestedState !== 'listening' && requestedState !== 'error') {
      if (DEBUG_ANIMATION) console.warn(`[ANIMATION] Unknown state '${state}' mapped to Idle`);
    }
    return clipName;
  }

  isOneShotClip(actionName) {
    return actionName && this.oneShotStates.has(actionName);
  }

  setState(state) {
    const requestedState = String(state || 'idle').toLowerCase().replace('waiting_for_approval', 'approval').replace('approval_required', 'approval');
    const normalizedState = requestedState === 'success' || requestedState === 'successful' ? 'happy' : requestedState;
    const nextState = normalizedState;
    const currentPriority = this.priority[this.state] ?? 10;
    const nextPriority = this.priority[nextState] ?? 10;

    if (nextState !== this.state && nextPriority < currentPriority) {
      if (DEBUG_ANIMATION) console.debug(`[ANIMATION] ignored lower-priority state: ${this.state.toUpperCase()} <- ${nextState.toUpperCase()}`);
      return;
    }

    if (this.state === nextState && this.currentActionName === this.stateToClipName(nextState)) {
      return;
    }

    this.state = nextState;
    if (this.state === 'dragging') this.dragging = true;
    if (this.state === 'dropping') this.dropStarted = performance.now();
    if (this.state !== 'dragging' && this.state !== 'dropping') this.dragging = false;

    if (!this.mixer) return;

    const targetName = this.stateToClipName(this.state);
    const target = this.actions.get(targetName) || this.actions.get('Idle');
    if (!target) {
      console.warn(`[ANIMATION] Missing clip '${targetName}' for state '${this.state}'`);
      return;
    }

    if (this.currentAction && this.currentAction !== target) {
      this.currentAction.fadeOut(this.fadeDuration);
    }
    if (this.currentAction !== target) {
      target.reset();
      target.fadeIn(this.fadeDuration);
      target.play();
      this.currentAction = target;
      this.currentActionName = targetName;
    }

    if (DEBUG_ANIMATION) console.debug(`[ANIMATION] ${targetName}`);
  }

  update(delta, lookX) {
    if (this.mixer) this.mixer.update(delta);

    if (this.dragging || this.state === 'dropping') {
      // The native Qt window is the draggable object. Do NOT translate the
      // Three.js root here or the model will move twice (inside the window
      // and with the window), producing the visible drag glitch.
      this.root.position.x = this.basePosition.x;
      this.root.position.y = this.basePosition.y;
      this.root.position.z = this.basePosition.z;
      this.root.rotation.x = THREE.MathUtils.damp(this.root.rotation.x, this.baseRotation.x + this.dragVelocity.y * 0.08, 10, delta);
      this.root.rotation.z = THREE.MathUtils.damp(this.root.rotation.z, this.baseRotation.z - this.dragVelocity.x * 0.12, 10, delta);
      if (this.state === 'dropping' && performance.now() - this.dropStarted >= 80) {
        this.state = 'idle';
        this.dragging = false;
      }
      return;
    }

    this.root.position.x = THREE.MathUtils.damp(this.root.position.x, this.basePosition.x, 5, delta);
    this.root.position.y = THREE.MathUtils.damp(this.root.position.y, this.basePosition.y, 5, delta);
    this.root.position.z = THREE.MathUtils.damp(this.root.position.z, this.basePosition.z, 5, delta);
    this.root.rotation.x = THREE.MathUtils.damp(this.root.rotation.x, this.baseRotation.x, 5, delta);
    this.root.rotation.y = THREE.MathUtils.damp(this.root.rotation.y, this.baseRotation.y + lookX * 0.04, 5, delta);
    this.root.rotation.z = THREE.MathUtils.damp(this.root.rotation.z, this.baseRotation.z, 5, delta);

    if (this.mouth && this.state === 'speaking') {
      const now = performance.now();
      if (now >= this.nextMouthPulse) {
        this.mouthTarget = Math.random() < 0.18 ? 0.9 : 0.25 + Math.random() * 0.55;
        this.nextMouthPulse = now + 120 + Math.random() * 220;
      }
      this.mouthOpen = THREE.MathUtils.damp(this.mouthOpen, this.mouthTarget, 8, delta);
      this.mouth.scale.y = this.mouthScale.y * (1 + this.mouthOpen);
      this.mouth.position.y = this.mouthPosition.y - this.mouthOpen * 0.004;
      return;
    }

    if (this.mouth) {
      this.mouthOpen = THREE.MathUtils.damp(this.mouthOpen, 0, 8, delta);
      this.mouth.scale.y = this.mouthScale.y * (1 + this.mouthOpen);
      this.mouth.position.y = this.mouthPosition.y - this.mouthOpen * 0.004;
    }
  }

  grab(point) {
    this.dragging = true;
    this.state = 'dragging';
    this.dragTarget.set(point.x, point.y, 0);
    this.dragPosition.copy(this.dragTarget);
    this.dragVelocity.set(0, 0, 0);
  }

  moveGrab(point) {
    if (this.dragging) this.dragTarget.set(point.x, point.y, 0);
  }

  release() {
    this.dragging = false;
    this.state = 'dropping';
    this.dropStarted = performance.now();
  }
}

new GLTFLoader().load('models/ai_ohto1_clean.glb', gltf => {
  model = gltf.scene;
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  model.position.sub(center);
  model.position.y += size.y / 2;
  const uniformScale = 1.8 / Math.max(size.x, size.y, size.z);
  model.scale.setScalar(uniformScale);
  console.log('Model scale:', model.scale.x, model.scale.y, model.scale.z);
  if (!(model.scale.x === model.scale.y && model.scale.y === model.scale.z)) {
    console.error('Model scale is not uniform');
  }
  scene.add(model);
  frameModel();

  const clipNames = (gltf.animations || []).map(clip => String(clip.name || '').trim()).filter(Boolean);
  console.info('[ANIMATION] available clips:', clipNames.join(', ') || '(none)');
  const missing = EXPECTED_CLIP_NAMES.filter(name => !clipNames.includes(name));
  if (missing.length) {
    console.warn('[ANIMATION] missing expected clips:', missing.join(', '));
  } else {
    console.info('[ANIMATION] expected clips present:', EXPECTED_CLIP_NAMES.join(', '));
  }
  if (gltf.animations && gltf.animations.length) {
    console.info('[ANIMATION] clip metadata', gltf.animations.map((clip, index) => ({
      index: index + 1,
      name: clip.name,
      duration: Number(clip.duration).toFixed(3),
      frames: clip.tracks.length ? Math.max(...clip.tracks.map(track => track.times.length)) : 0,
      trackCount: clip.tracks.length,
    })));
  } else {
    console.warn('[ANIMATION] no GLB animation clips detected');
  }

  animationController = new AnimationController(model, gltf.animations || []);
  window.astraModelLoaded = true;
  if (window.DEBUG_UI) console.info('ASTRA_MODEL_LOADED');
  console.info(`GLB loaded: meshes=${model.children.length} clips=${gltf.animations.length}`);
  animationController.setState('idle');
  loading.textContent = gltf.animations.length ? `${gltf.animations.length} verified clips ready` : 'No exported clips detected';
  setTimeout(() => loading.classList.add('hidden'), 1400);
}, undefined, error => { window.astraModelLoaded = false; console.error(`GLB load error: ${error?.message || error}`); loading.textContent = 'Model failed to load'; status.textContent = `GLB load error: ${error?.message || error}`; status.classList.remove('hidden'); });

function playState(name) {
  animationController?.setState(name);
}
function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  animationController?.update(delta, pointer.x);
  renderer.render(scene, camera);
}
animate();

function addMessage(role, text) { const item = document.createElement('div'); item.className = `message ${role}`; item.innerHTML = `<b>${role === 'user' ? 'YOU' : 'ASTRA'}</b>${escapeHtml(text)}`; messages.append(item); messages.scrollTop = messages.scrollHeight; }
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }
function openChat() { menu.classList.add('hidden'); chat.classList.remove('hidden'); document.querySelector('#chat-input').focus(); }
function closePopups() { menu.classList.add('hidden'); approval.classList.add('hidden'); }

document.querySelector('#chat-form').addEventListener('submit', event => { event.preventDefault(); const input = document.querySelector('#chat-input'); const text = input.value.trim(); if (!text || !backend) return; addMessage('user', text); input.value = ''; backend.ask(text); });
document.querySelector('#close-chat').onclick = () => chat.classList.add('hidden');
document.querySelector('#chat-mic').onclick = () => { backend?.listen_once(); playState('listening'); };
document.querySelector('#approve').onclick = () => { backend.approve(approval.dataset.planId); approval.classList.add('hidden'); };
document.querySelector('#reject').onclick = () => { backend.reject(approval.dataset.planId); approval.classList.add('hidden'); };

document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => {
  const action = button.dataset.action;
  if (action === 'talk' || action === 'mic') { backend?.listen_once(); playState('listening'); }
  if (action === 'pause') playState('idle');
  if (action === 'settings') openChat();
  if (action === 'reset') host?.reset_position();
  if (action === 'top') { settings.always_on_top = !settings.always_on_top; host?.set_always_on_top(settings.always_on_top); }
  if (['small','normal','large'].includes(action)) { scale = { small: .72, normal: 1, large: 1.3 }[action]; frameModel(); host?.set_companion_scale(scale); }
  if (action === 'edge') { settings.edge_behavior = !settings.edge_behavior; host?.set_edge_behavior(settings.edge_behavior); }
  if (action === 'exit') window.close();
  closePopups();
}));

canvas.addEventListener('pointermove', event => {
  pointer.x = (event.clientX / innerWidth) * 2 - 1;
  pointer.y = -(event.clientY / innerHeight) * 2 + 1;
  if (event.pointerId !== activePointerId) return;
  if (dragging && animationController?.dragging) animationController.moveGrab(canvasPoint(event));
  if (dragging && host) {
    latestScreen.x = event.screenX;
    latestScreen.y = event.screenY;
    if (dragPositionReady) {
      const deltaX = event.screenX - dragStartScreen.x;
      const deltaY = event.screenY - dragStartScreen.y;
      const nextX = Math.round(dragWindowOrigin.x + deltaX);
      const nextY = Math.round(dragWindowOrigin.y + deltaY);
      host.move_companion(nextX, nextY);
    }
  }
});

function frameModel() {
  if (!model) return;
  const bounds = new THREE.Box3().setFromObject(model);
  const size = bounds.getSize(new THREE.Vector3());
  const targetY = size.y * .46;
  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
  const verticalDistance = size.y / (2 * Math.tan(verticalFov / 2));
  const horizontalDistance = size.x / (2 * Math.tan(horizontalFov / 2));
  const distance = Math.max(verticalDistance, horizontalDistance, size.z) * 1.8 / Math.max(scale, .72);
  camera.position.set(0, targetY, distance);
  camera.lookAt(0, targetY, 0);
}
canvas.addEventListener('pointerdown', event => {
  if (event.button !== 0) return;
  activePointerId = event.pointerId;
  dragging = true;
  dragPositionReady = false;
  dragStartScreen.x = event.screenX;
  dragStartScreen.y = event.screenY;
  latestScreen.x = event.screenX;
  latestScreen.y = event.screenY;
  dragWindowOrigin = { x: Number(settings.x) || 80, y: Number(settings.y) || 120 };
  animationController?.setState('dragging');
  animationController?.grab(canvasPoint(event));
  if (host && typeof host.get_position === 'function') {
    // QWebChannel returns slot results asynchronously. The previous code
    // treated get_position() as synchronous, so it silently fell back to
    // (80,120) and caused the window to jump on drag start.
    host.get_position(current => {
      if (!dragging || current == null) return;
      const x = Number(current.x);
      const y = Number(current.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      dragWindowOrigin.x = x;
      dragWindowOrigin.y = y;
      dragPositionReady = true;
      const deltaX = latestScreen.x - dragStartScreen.x;
      const deltaY = latestScreen.y - dragStartScreen.y;
      host.move_companion(Math.round(x + deltaX), Math.round(y + deltaY));
    });
  } else {
    dragPositionReady = true;
  }
  logUi('drag started', { x: dragWindowOrigin.x, y: dragWindowOrigin.y, screen: { x: event.screenX, y: event.screenY } });
  canvas.classList.add('dragging');
  canvas.setPointerCapture(event.pointerId);
});
function endDrag(event) {
  if (event.pointerId !== activePointerId) return;
  dragging = false;
  dragPositionReady = false;
  activePointerId = null;
  animationController?.release();
  logUi('drag ended', { x: dragWindowOrigin.x, y: dragWindowOrigin.y });
  canvas.classList.remove('dragging');
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
}
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);
canvas.addEventListener('dblclick', () => { backend?.listen_once(); playState('listening'); });
canvas.addEventListener('contextmenu', event => { event.preventDefault(); menu.classList.toggle('hidden'); });
document.addEventListener('pointerdown', event => { if (!event.target.closest('#menu') && !event.target.closest('#scene')) closePopups(); });

window.astraStatus = payload => { if (payload.ai.includes('OFFLINE') || payload.ai.includes('MISSING')) { status.textContent = `AI ${payload.ai}`; status.classList.remove('hidden'); } };
window.__astraPending.status.splice(0).forEach(window.astraStatus);
window.astraEvent = payload => {
  if (payload.type === 'transcript') { window.astraTranscript(payload); return; }
  const state = (payload.state || 'idle').toLowerCase().replace('waiting_for_approval', 'approval').replace('approval_required', 'approval');
  logUi(`state: ${state}`, payload);
  document.querySelector('#state').textContent = state;
  document.querySelector('#speaking').classList.toggle('hidden', state !== 'speaking');
  if (state === 'speaking') logUi('TTS started');
  if (state === 'idle' && (payload.previousState === 'speaking' || payload.type === 'state')) logUi('TTS finished');
  playState(state);
};
window.__astraPending.event.splice(0).forEach(window.astraEvent);
window.astraTranscript = payload => { if (payload.text) addMessage('user', payload.text); };
window.__astraPending.transcript.splice(0).forEach(window.astraTranscript);
window.astraResponse = payload => {
  logUi('backend response', payload);
  if (payload.status === 'approval_required') {
    logUi('approval required', payload);
    approval.dataset.planId = payload.plan_id;
    document.querySelector('#approval-goal').textContent = payload.goal;
    document.querySelector('#approval-steps').textContent = payload.steps.map(step => `${step.tool}: ${step.reason}`).join('\n');
    approval.classList.remove('hidden');
    return;
  }
  if (payload.response) addMessage('assistant', payload.response);
};
window.__astraPending.response.splice(0).forEach(window.astraResponse);
