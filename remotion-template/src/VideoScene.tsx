import { AbsoluteFill } from "remotion";

export const totalFrames = 30;
export const fps = 30;
export const width = 1280;
export const height = 720;

export const VideoScene = () => (
  <AbsoluteFill className="scene-canvas bg-slate-950">
    <div className="scene-title m-auto text-white">Remotion</div>
  </AbsoluteFill>
);
