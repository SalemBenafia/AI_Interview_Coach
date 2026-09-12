"use client";

import { Room } from "livekit-client";

export {
  Room,
  RoomEvent,
  Track,
} from "livekit-client";

export type {
  RemoteTrack,
  RemoteTrackPublication,
} from "livekit-client";

export function createRoom(): Room {
  return new Room({
    adaptiveStream: true,
    dynacast: true,
    audioCaptureDefaults: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
}

export async function connectToRoom(room: Room, url: string, token: string) {
  await room.connect(url, token, { autoSubscribe: true });
}

export async function attachRemoteAudio(
  track: any,
  audioElement: HTMLAudioElement
) {
  if (typeof window === "undefined") return;
  if (!audioElement) return;
  track.attach(audioElement);
}
