// file: declarations.d.ts
declare module 'mic-recorder-to-mp3' {
  class MicRecorder {
    constructor(options?: any);
    start(): Promise<void>;
    stop(): {
      getMp3(): Promise<[any, Blob]>;
    };
  }
  export default MicRecorder;
}