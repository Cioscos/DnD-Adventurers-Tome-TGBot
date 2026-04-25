// webapp/src/dice/physics/faceDetector.ts
import * as THREE from 'three'

export function faceUp(
  faceNormals: Record<number, THREE.Vector3>,
  bodyQuat: THREE.Quaternion,
  worldTarget: THREE.Vector3 = new THREE.Vector3(0, 1, 0),
): { value: number; dot: number } {
  const tmp = new THREE.Vector3()
  let bestValue = Number(Object.keys(faceNormals)[0])
  let bestDot = -Infinity
  for (const [value, normal] of Object.entries(faceNormals)) {
    tmp.copy(normal).applyQuaternion(bodyQuat)
    const dot = tmp.dot(worldTarget)
    if (dot > bestDot) {
      bestDot = dot
      bestValue = Number(value)
    }
  }
  return { value: bestValue, dot: bestDot }
}

export function quaternionForFace(
  faceNormals: Record<number, THREE.Vector3>,
  targetFace: number,
  currentQuat: THREE.Quaternion,
  worldTarget: THREE.Vector3 = new THREE.Vector3(0, 1, 0),
): THREE.Quaternion {
  const targetNormal = faceNormals[targetFace]
  if (!targetNormal) return currentQuat.clone()
  const currentTargetWorld = targetNormal.clone().applyQuaternion(currentQuat).normalize()
  const desired = worldTarget.clone().normalize()
  const correction = new THREE.Quaternion().setFromUnitVectors(currentTargetWorld, desired)
  return correction.multiply(currentQuat)
}
