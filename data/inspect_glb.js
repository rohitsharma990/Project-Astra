const fs = require('fs');
const path = 'C:/Users/rohit/Desktop/Python/Project-Astra/ui/models/ai_ohto1_animated.glb';
const buf = fs.readFileSync(path);
console.log('magic', buf.readUInt32LE(0).toString(16), 'version', buf.readUInt32LE(4));
let offset = 12;
let found = false;
while (offset + 8 <= buf.length) {
  const length = buf.readUInt32LE(offset);
  const chunkType = buf.readUInt32LE(offset + 4);
  const chunk = buf.subarray(offset + 8, offset + 8 + length);
  offset += 8 + length;
  if (chunkType === 0x4E4F534A) {
    const gltf = JSON.parse(chunk.toString('utf8'));
    const anims = gltf.animations || [];
    console.log('animation_count', anims.length);
    anims.forEach((anim, idx) => {
      console.log(`${idx}: name=${anim.name} duration=${Number(anim.duration).toFixed(3)} channels=${(anim.channels || []).length} samplers=${(anim.samplers || []).length}`);
    });
    found = true;
    break;
  }
}
if (!found) console.log('NO_JSON_CHUNK_FOUND');
