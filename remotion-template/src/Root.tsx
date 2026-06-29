import { Composition } from "remotion";
import { VideoScene, totalFrames } from "./VideoScene";

export const Root = () => (
  <Composition
    id="VideoScene"
    component={VideoScene}
    durationInFrames={totalFrames}
    fps={30}
    width={1280}
    height={720}
  />
);
