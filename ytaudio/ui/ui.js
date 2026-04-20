const API_URL = "";

const ui = {
  audio: document.getElementById("audio"),
  search: document.getElementById("searchInput"),
  results: document.getElementById("results"),
  trackname: document.getElementById("trackname"),
  play: document.getElementById("play"),
  play_ffwd: document.getElementById("play-ffwd"),
  play_rev: document.getElementById("play-rev"),
  time_current: document.getElementById("time_current"),
  time_total: document.getElementById("time_total"),
  playedBar: document.getElementById("playedBar"),
  bufferedBar: document.getElementById("bufferedBar"),
  progressBar: document.getElementById("progressBar"),
  playlist: document.getElementById("playlist"),
  playlist_toggle: document.getElementById("playlist-toggle"),
  dialog: document.getElementById("dialog")
};

// Use AudioContext (for EQ ad Filter)
const ctx = new AudioContext();
ui.source = ctx.createMediaElementSource(ui.audio);
async function unlockAudio() {
  if (ctx.state !== "running") {
    await ctx.resume();
  }
}
["click", "touchstart", "keydown"].forEach(evt => {
  document.addEventListener(evt, unlockAudio, { once: true });
});


/* ---------------- API Auth -------------- */

// Store a new API key in local storage.
const updated_key = new URLSearchParams(window.location.search).get("key");
if (updated_key) {
  localStorage.api_key = updated_key;
  alert("🧒 Welcome")
  window.location = window.location.href.split("?")[0];
}

// Perform xhr request including API key headers.
async function fetch_auth(url, options = {}) {
  const headers = {
    ...(options.headers || {}),
    "X-API-Key": localStorage.api_key
  };

  const response = await fetch(url, {
    ...options,
    headers
  });

  if (response.status === 401) {
    console.error("Unauthorized - invalid API key");
    alert("🧒 Please kindly ask for a valid API key");
  }
  return response;
}

/* ---------------- HELPERS --------------- */

function get_track_duration() {
  // NOTE: In Chrome, ui.audio.duration is Infinity without Content-Length, ie. when using route /stream/mp3.
  // return isFinite(ui.audio.duration) ? ui.audio.duration : playlist[playlist_position]?.duration;
  return playlist[playlist_position]?.duration ? playlist[playlist_position]?.duration : ui.audio.duration;
}

function get_provider_image(provider) {
  return {
    'bandcamp': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/Bandcamp-button-bc-circle-green.svg/960px-Bandcamp-button-bc-circle-green.svg.png',
    'soundcloud': 'https://cdn-icons-png.flaticon.com/512/145/145809.png',
    'youtube': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/YouTube_full-color_icon_%282024%29.svg/1280px-YouTube_full-color_icon_%282024%29.svg.png'
  }[provider] || '';  // FIXME
}

function formatTime(t, fallback) {
  if (!isFinite(t) || t == null) return fallback || '?:??';
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.textContent;
}

const SCROLL_EDGE_THRESHOLD = 16; // px from top/bottom
const SCROLL_SPEED = 1;           // px per frame
let autoScrollActive = false;
document.addEventListener("dragover", (e) => {
  // Scroll on drag (for playlist)
  const container = ui.playlist;
  const rect = container.getBoundingClientRect();
  const offsetY = e.clientY - rect.top;
  // Near top
  if (offsetY < SCROLL_EDGE_THRESHOLD) {
    container.scrollTop -= SCROLL_SPEED;
    autoScrollActive = true;
  }
  // Near bottom
  else if (offsetY > rect.height - SCROLL_EDGE_THRESHOLD) {
    container.scrollTop += SCROLL_SPEED;
    autoScrollActive = true;
  } else {
    autoScrollActive = false;
  }
});

/* ---------------- SEARCH ---------------- */

function isURL(str) {
  return str.startsWith("http://") || str.startsWith("https://");
}

async function search() {
  const q = ui.search.value.trim();
  if (q.length < 1) return;
  window.location.hash = q;  // store search in URL hash

  // 🔥 Direct play if URL
  if (isURL(q)) {
    // play_url(q);                             // do not save in playlist
    play_position(playlist_enqueue({url: q}));  // do save in playlist
    return;
  }

  ui.search.blur();
  ui.search.parentNode.querySelector("button").disabled = true;
  ui.results.innerHTML = `🎶 Searching for <q>${escapeHTML(q)}</q>...`;

  let data;
  try {
    const res = await fetch_auth(`${API_URL}/search?q=${encodeURIComponent(q)}`);
    data = await res.json();
  } catch(e) {
    // FIXME: Doesn't execute when response is 500 (with valid json eror detail).
    alert(`❌ Search failed. Please try again.\n\n${String(e)}`);
    ui.results.innerHTML = "";
    throw(e);
  } finally {
    ui.search.parentNode.querySelector("button").disabled = false;
  }

  ui.results.innerHTML = "";
  data.forEach(track => {
    const div = document.createElement("div");
    div.className = "result-item row";
    div.innerHTML = `
      <div style="position:relative">
        <img class="thumbnail" style="display:block" src="${track.thumbnail}" alt="">
        <button class="result-play" style="position:absolute; bottom:2px; right:2px">
          ▶︎
        </button>
        <button class="result-enqueue" style="position:absolute; bottom:2px; right:2px">
          ≡
        </button>
      </div>
      <div style="flex:1;">
        <p><strong>${escapeHTML(track.title)}</strong></p>
        <p>${escapeHTML(track.channel)}</p>
        <p style="color:var(--color-mute)">${formatTime(track.duration, '&nbsp;')}</p>
      </div>
      <img class="result-info" style="align-self:center; width:24px;" alt="${track.provider}" src="${get_provider_image(track.provider)}" alt="">
    `;

    div.querySelector("button.result-play").onclick = () => play_position(playlist_enqueue(track));
    div.querySelector("button.result-enqueue").onclick = () => playlist_enqueue(track);
    div.querySelector(".result-info").onclick = () => display_trackinfo(track);

    ui.results.appendChild(div);
  });
}
document.addEventListener("DOMContentLoaded", () => {
  // Restore search from URL hash
  const q = decodeURIComponent(window.location.hash.substr(1));
    if (q) {
      ui.search.value = q;
      search();
    }
});

/* --------------- PLAYLIST --------------- */

const playlist = JSON.parse(localStorage.playlist || null) || [];
let playlist_position = parseInt(localStorage.playlist_position) || 0;  // Private
// const playlist = [{"url":"https://songforberta.bandcamp.com/track/song-for-berta-unmixed-demo","title":"Song for Berta - Unmixed Demo","channel":"by Damien Rice, JFDR, Sandrayati Fay","thumbnail":"https://f4.bcbits.com/img/a2705409571_7.jpg","description":"tags:Acoustic,Honduras,acoustic","duration":null,"provider":"bandcamp"},{"url":"https://marcgartman.bandcamp.com/track/damien","title":"DAMIEN","channel":"by DAMIEN","thumbnail":"https://f4.bcbits.com/img/a2686841425_7.jpg","description":"tags:electronic,acoustic,UnitedStates,bedroom-pop,popelectronic,singersongwriter;folk,Minnesota,Rock,Duluth","duration":null,"provider":"bandcamp"},{"url":"https://onnset.bandcamp.com/track/damien-schneider-seti-ansome-remix","title":"Damien Schneider - Seti (Ansome Remix)","channel":"from ONNST003 - Damien Schneider - Seti EP (Ansome Remix) by Damien Schneider","thumbnail":"https://f4.bcbits.com/img/a2602295058_7.jpg","description":"","duration":null,"provider":"bandcamp"}];

function playlist_get_position_by_url(url) {
  for (const [position, track] of playlist.entries()) if (track.url == url) return position;
}

function playlist_enqueue(track) {
  // if (!parseInt(localStorage.playlist_visible)) playlist_toggle();
  const position = playlist_get_position_by_url(track.url);
  if (position !== undefined) {
    // TODO: Move track to end of playlist ?
    ui.playlist.children[position].scrollIntoView({behavior:"smooth"});
    return position;
  } else {
    // append track to playlist
    if (track.url) playlist.push(track);
    track.date_added = Date.now();  // save the timestamp
    playlist_redraw();
    return playlist.length-1;
  }
}

function playlist_dequeue(position) {
  if (!Number.isInteger(position)) return;
  if (confirm(`♪ ${playlist[position].title}\n\nRemove track from playlist ?`)) {
    playlist.splice(position, 1);
    if (position == playlist_position) playlist_position = null;
    playlist_redraw();
  }
}

let dragIndex = null;
function playlist_redraw() {
  // Save playlist to local storage
  localStorage.playlist = JSON.stringify(playlist);
  localStorage.playlist_position = playlist_position;

  // Redraw playlist
  ui.playlist.innerHTML = playlist.length ? '' : 'Playlist is empty. Just search and play some music !';
  for (const [i, track] of playlist.entries()) {
    const wrapper = document.createElement("div");

    wrapper.innerHTML = `
      <div class="playlist-item row" draggable="true" style="gap:12px; align-items:center">
        <button class="playlist-play">▶︎</button>
        <img style="width:24px" src="${track.thumbnail}" alt="">
        <span style="flex:1">
          ${track.title}
        </span>
        <span class="duration">
          ${(track.duration) ? formatTime(track.duration) : ''}
        </span>
        <img class="playlist-info" style="width:16px" src="${get_provider_image(track.provider)}" alt="">
        <button class="playlist-remove">╳</button>
      </div>
    `;

    const item = wrapper.querySelector(".playlist-item");

    // Highlight track currently playing
    if (i == playlist_position) {
      item.classList.add("current-position");
    }

    // Click events
    item.querySelector(".playlist-play").addEventListener("click", () => play_position(i));
    item.querySelector(".playlist-remove").addEventListener("click", () => playlist_dequeue(i));
    item.querySelector(".playlist-info").addEventListener("click", () => display_trackinfo(playlist[i]));

    // Drag events
    item.addEventListener("dragstart", () => dragIndex = i);
    item.addEventListener("dragover", (e) => e.preventDefault());  // REQUIRED for drop
    item.addEventListener("drop", () => {
      if (dragIndex === null || dragIndex === i) return;
      const playlist_position_url = playlist[playlist_position].url;  // Save playlist position
      const moved = playlist.splice(dragIndex, 1)[0];
      playlist.splice(i, 0, moved);
      dragIndex = null;
      console.log(playlist_position, playlist_get_position_by_url(playlist_position_url), playlist_position_url)
      playlist_position = playlist_get_position_by_url(playlist_position_url);  // Restore playlist position
      playlist_redraw();  // FIXME: Update playlist_position.
    });

    ui.playlist.appendChild(wrapper);
  }
}
playlist_redraw();

// Playlist display toggle
function playlist_toggle() {
  // TODO: Make tri-state toggle: collapsed, displayed (height:21vh), expanded (height:100vh-playerheight)
  if (ui.playlist.parentNode.style.display) {
    ui.playlist.parentNode.style.display =  "";
    ui.playlist_toggle.classList.add("active");
    localStorage.playlist_visible = 1;
  } else {
    ui.playlist.parentNode.style.display = "none";
    ui.playlist_toggle.classList.remove("active");
    localStorage.playlist_visible = 0;
  }
}
ui.playlist_toggle.addEventListener("click", playlist_toggle);
if (!parseInt(localStorage.playlist_visible)) {
  playlist_toggle();
}

/* ---------------- PLAYER ---------------- */

/**
 * Play position in playlist. Main entry point for playing.
 */
function play_position(position) {
  if (!Number.isInteger(position) || position < 0 || position > playlist.length-1) {
    console.error("Play position is outside playlist range", position);
    return;
  }
  playlist_position = position;
  playlist_redraw();
  ui.playlist.children[position].scrollIntoView({behavior:"smooth"});
  const track = playlist[position];
  console.log('Playing playlist position', position, track);
  play_url(track.url);
}

async function play_url(url) {
  // TODO: Extract load logic into function `load_url(url)` ?
  ui.play.innerHTML = "⌛";
  ui.trackname.innerHTML = '♪ Loading track...'

  console.debug('Loading info for URL', url);
  const info_res = await fetch_auth(`${API_URL}/info?url=${encodeURIComponent(url)}`)
  const info = await info_res.json();
  ui.trackname.innerHTML = escapeHTML(info.title || 'Unknown track name');

  // Re-save track info in playlist (for direct URL play, and bandcamp search results missing duration)
  const playlist_track = playlist[playlist_get_position_by_url(url)];
  if (playlist_track) {
    playlist_track.title = info.title;
    playlist_track.duration = info.duration;
    playlist_track.thumbnail = info.thumbnail;
    playlist_redraw();
  }

  // Play direct URL
  try {
    console.debug(`Playing direct stream URL (${info.acodec})`, info.url);
    ui.audio.src = info.url;
    await ui.audio.play();
    return;
  } catch(e) {
    console.log('Failed to play direct URL', e);
  }

  // Play fallback proxy URL (mp3 transcoded)
  try {
    const proxy_url = `${API_URL}/stream/mp3?url=${encodeURIComponent(url)}`;
    console.log('Playing fallback proxy URL (mp3)', proxy_url);
    ui.audio.src = proxy_url;
    await ui.audio.play();
  } catch(e) {
    console.error('Playback error', e);
    if (e.name == "AbortError") return;  // skip user aborted error
    if (e.name == "NotAllowedError") {
      alert("🎼 Press play to start music.");  // this error is raised on autoplay
      return;
    }
    alert(`❌ Playback failed. Please try again.\n\n${String(e)}`);
    ui.trackname.innerHTML = '';
    throw(e);
  }
}

// Playback buttons (play/pause, ffwd, rev)
async function play_toggle() {
  if (ui.play.disabled) return;
  const audio_loaded = ui.audio.readyState >= 4;
  if (ui.audio.paused) {
    if (audio_loaded) {
      await ui.audio.play();  // if audio is loaded, then play the audio
    } else if (playlist.length) {
      play_position(playlist_position);  // if no audio is loaded, then play the position in playlist
    } else {
      alert("𝄞 Please search for music to play !");  // if nothing to play
    }
  } else {
    ui.audio.pause();
  }
}
function play_ffwd() {
  ui.audio.currentTime += 5;
}
function play_rev() {
  ui.audio.currentTime -= 5;
}
ui.play.addEventListener("click", play_toggle);
ui.play_ffwd.addEventListener("click", play_ffwd);
ui.play_rev.addEventListener("click", play_rev);

// Enable/disable state and icon of play button
function play_enable(enable) {
  if (enable) {
    const icon = ui.audio.paused ? "▶︎" : "⏸︎";
    ui.play.innerHTML = icon;
    ui.play.disabled = false;
    ui.play.classList.remove("active");
  } else {
    ui.play.innerHTML = "⌛";
    ui.play.disabled = true;
    ui.play.classList.add("active");
  }
}
play_enable(true);  // Initalize as enabled
ui.audio.addEventListener("canplay", () => play_enable(true));
ui.audio.addEventListener("loadstart", () => play_enable(false));
ui.audio.addEventListener("waiting", () => play_enable(false));
ui.audio.addEventListener("play", () => play_enable(true));
ui.audio.addEventListener("pause", () => play_enable(true));

// Play next track in playlist (on track end)
function play_next() {
  const next = playlist_position+1;
  if (next < playlist.length) play_position(next);
  else console.log("Playlist ended");
}
ui.audio.addEventListener("ended", play_next);

// Display of track playback time & progress bar
ui.audio.addEventListener("timeupdate", () => {
  const current = ui.audio.currentTime;
  const duration = get_track_duration();

  ui.time_current.textContent = formatTime(current);
  ui.time_total.textContent = formatTime(duration);
  if (duration > 0) {
    ui.playedBar.style.width = (current / duration * 100) + "%";
  }
});
ui.audio.addEventListener("progress", () => {
  const duration = get_track_duration();
  if (ui.audio.buffered.length > 0 && duration > 0) {

    const bufferedEnd = ui.audio.buffered.end(ui.audio.buffered.length - 1);

    const percent = (bufferedEnd / duration) * 100;
    ui.bufferedBar.style.width = percent + "%";
  }
});

// Track seeking on progress bar
function play_seek(clientX) {
  if (!ui.audio.duration) return;
  const duration = get_track_duration();
  const rect = ui.progressBar.getBoundingClientRect();
  const ratio = (clientX - rect.left) / rect.width;
  const targetTime = ratio * (duration);
  console.log("Seeking to", targetTime)
  ui.audio.currentTime = targetTime;
}
ui.progressBar.addEventListener("click", (e) => play_seek(e.clientX));  // Desktop
ui.progressBar.addEventListener("touchstart", (e) => play_seek(e.touches[0].clientX));  // Mobile

/* ----------- TRACK INFO DIALOG ----------- */

function display_trackinfo(track) {
  // Thumbnail and page URL
  ui.dialog.querySelector("#dialog-content").innerHTML = `
    <div>
      <img style="height:120px" src="${track.thumbnail}">
    </div>
    <p style="flex:1">
      <a target="_blank" href="${track.url}">${escapeHTML (track.url)}</a>
    </p>
  `;

  // Track metadata
  const div = document.createElement('div');
  for (let [key, value] of Object.entries(track)) {
    if (key == "thumbnail") continue;
    if (key == "url") continue;
    if (key == "description") continue;
    if (key == "acodec") continue;
    if (key == "duration") value = formatTime(value);
    if (key == "date_added") value = new Date(value).toLocaleString();
    div.innerHTML += `
      <p>
        <strong style="text-transform:capitalize; color: var(--color-mute)">
          ${key.replace("_", " ")}
        </strong>
        <span>
          ${escapeHTML(value)}
        </span>
      </p>
    `;
  }
  ui.dialog.querySelector("#dialog-content").appendChild(div);
  ui.dialog.showPopover();
}

/* ------------------ EQ ------------------- */

const low = ctx.createBiquadFilter();
low.type = "lowshelf";
low.frequency.value = 200;
low.Q.value = .85;

const mid = ctx.createBiquadFilter();
mid.type = "peaking";
mid.frequency.value = 1000;
mid.Q.value = .95;

const high = ctx.createBiquadFilter();
high.type = "highshelf";
high.frequency.value = 4000;
high.Q.value = .75;

// Filter (Mixxx-style)
const lp = ctx.createBiquadFilter();
lp.type = "lowpass";
lp.frequency.value = 20000;
lp.Q.value = 2;

const hp = ctx.createBiquadFilter();
hp.type = "highpass";
hp.frequency.value = 20;
hp.Q.value = 2;

const lpGain = ctx.createGain();
const hpGain = ctx.createGain();

// Routing
ui.source.connect(low);
low.connect(mid);
mid.connect(high);

// split for filter
const dryGain = ctx.createGain();

high.connect(dryGain);
dryGain.connect(ctx.destination);

high.connect(lp);
lp.connect(lpGain);
lpGain.connect(ctx.destination);

high.connect(hp);
hp.connect(hpGain);
hpGain.connect(ctx.destination);

function applyFilter(v) {
  const now = ctx.currentTime;

  if (v < 0) {
    const amt = -v;

    const freq = 20000 * Math.pow(0.01, amt);
    lp.frequency.setTargetAtTime(freq, now, 0.01);

    dryGain.gain.setTargetAtTime(1 - amt, now, 0.01);
    lpGain.gain.setTargetAtTime(amt, now, 0.01);
    hpGain.gain.setTargetAtTime(0, now, 0.01);

  } else if (v > 0) {
    const amt = v;

    const freq = 20 * Math.pow(1000, amt);
    hp.frequency.setTargetAtTime(freq, now, 0.01);

    dryGain.gain.setTargetAtTime(1 - amt, now, 0.01);
    hpGain.gain.setTargetAtTime(amt, now, 0.01);
    lpGain.gain.setTargetAtTime(0, now, 0.01);

  } else {
    // TRUE neutral (important!)
    dryGain.gain.setTargetAtTime(1, now, 0.01);
    lpGain.gain.setTargetAtTime(0, now, 0.01);
    hpGain.gain.setTargetAtTime(0, now, 0.01);
  }
}

function setupKnobs() {
  document.querySelectorAll(".knob").forEach(knob => {
    const dial = knob.querySelector(".knob-dial");
    const param = knob.dataset.param;

    let value = 0; // -1 → +1
    let dragging = false;
    let startY = 0;

    let lastTap = 0; // for double-tap

    function clamp(v) {
      return Math.max(-1, Math.min(1, v));
    }

    function updateVisual() {
      const angle = value * 135;
      dial.style.transform = `rotate(${angle}deg)`;
    }

    function applyAudio() {
      switch (param) {
        case "low":
          low.gain.setTargetAtTime(value * 12, ctx.currentTime, 0.01);
          break;
        case "mid":
          mid.gain.setTargetAtTime(value * 12, ctx.currentTime, 0.01);
          break;
        case "high":
          high.gain.setTargetAtTime(value * 12, ctx.currentTime, 0.01);
          break;
        case "filter":
          applyFilter(value);
          break;
      }
    }

    function setValue(v) {
      value = clamp(v);
      updateVisual();
      applyAudio();
    }

    function onPointerDown(e) {
      e.preventDefault();

      const now = Date.now();
      const delta = now - lastTap;
      lastTap = now;

      // Double tap / double click → reset
      if (delta < 300) {
        setValue(0);
        return;
      }

      dragging = true;
      startY = e.clientY;
      dial.setPointerCapture?.(e.pointerId);
      dial.style.cursor = "grabbing";
    }

    function onPointerMove(e) {
      if (!dragging) return;

      const delta = (startY - e.clientY) / 100;
      startY = e.clientY;

      setValue(value + delta);
    }

    function onPointerUp(e) {
      dragging = false;
      dial.releasePointerCapture?.(e.pointerId);
      dial.style.cursor = "grab";
    }

    // Pointer events (works for mouse + touch + pen)
    dial.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);

    // Desktop fallback (dblclick explicitly)
    dial.addEventListener("dblclick", () => setValue(0));

    // Prevent page scroll while dragging on mobile
    dial.addEventListener("touchstart", e => e.preventDefault(), { passive: false });

    // Init
    setValue(0);
  });
}

setupKnobs();

/* ---------------- HOTKEYS ---------------- */

document.addEventListener("keydown", (e) => {

  if (["INPUT"].includes(e.target.tagName)) return;

  let preventDefault = true;
  if      (e.code == "Space")      play_toggle();
  else if (e.code == "ArrowRight") play_ffwd();
  else if (e.code == "ArrowLeft")  play_rev();
  else if (e.code == "Tab")        ui.search.focus();
  else preventDefault = false;

  if (preventDefault) e.preventDefault();
  if (preventDefault) console.log('Hotkey prevented default')
});

// Debug
ui.audio.addEventListener("loadstart", () => console.log("loadstart"));
ui.audio.addEventListener("loadedmetadata", () => console.log("metadata loaded"));
ui.audio.addEventListener("canplay", () => console.log("can play"));
ui.audio.addEventListener("waiting", () => console.log("waiting"));
ui.audio.addEventListener("stalled", () => console.log("stalled"));
ui.audio.addEventListener("ended", (e) => console.log("ended", e));