import { Composition } from "remotion";
import { VideoScene, totalFrames, fps, width, height } from "./VideoScene";
import "./index.css";

export const Root = () => (
  <Composition
    id="VideoScene"
    component={VideoScene}
    durationInFrames={totalFrames}
    fps={fps}
    width={width}
    height={height}
  />
);
