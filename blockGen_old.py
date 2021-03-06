from flask import Flask, escape, request
import azure.cognitiveservices.speech as speechsdk
import json, time
from celery import Celery, Task
from celery_config import celery_app


speechKey, serviceRegion = "513d717444344d14bfe15708468aa8b6", "westus"
speechConfig = speechsdk.SpeechConfig(subscription=speechKey, region=serviceRegion)
speechConfig.request_word_level_timestamps()

currentOffset = 0
pauseThreshold = 10000000;
wordCountThreshold = 20; #TODO, CHANGE ARBITRARY VALUES
emptyBlock = {
    "text":"",
    "offset":0,
    "duration":-1
}

def onSpeechStart(evt):
    global speechSessions
    print('Session started: {}'.format(evt))

def onRecognized(evt, block_dict):
    print('Recongized: {}'.format(evt))
    block_dict['blockArray'] = block_dict['blockArray'] + genBlocks(evt.result)

def onSpeechStop(evt, speechRecognizer, block_dict):
    block_dict['done'] = True;
    print('Session stopped/canceled: {}'.format(evt))
    print("donezo")
    speechRecognizer.stop_continuous_recognition_async()

    speechRecognizer.regognizing.disconnect_all()
    speechRecognizer.recognized.disconnect_all()
    speechRecognizer.session_started.disconnect_all()
    speechRecognizer.session_stopped.disconnect_all()
    speechRecognizer.canceled.disconnect_all()

# class TestClass(celery_app.Task):
#     # def onSpeechStart(self, evt):
#     #     global speechSessions
#     #     print('Session started: {}'.format(evt))
#     #
#     # def onRecognized(self, evt, block_dict):
#     #     print('Recongized: {}'.format(evt))
#     #     block_dict['blockArray'] = block_dict['blockArray'] + genBlocks(evt.result)
#     #
#     # def onSpeechStop(self, evt, speechRecognizer, block_dict):
#     #     block_dict['done'] = True;
#     #     print('Session stopped/canceled: {}'.format(evt))
#     #     print("donezo")
#     #     speechRecognizer.stop_continuous_recognition_async()
#     #
#     # def createBlockData(self, filepath="data/whatstheweather.wav"):
#     #     global speechKey, serviceRegion, speechConfig, currentOffset, pauseThreshold, wordCountThreshold, emptyBlock
#     #
#     #     print("here")
#     #     block_dict = {'blockArray': [], 'done': False}
#     #     filename = "data/bee movie.wav"
#     #     audioConfig = speechsdk.audio.AudioConfig(filename=filepath)
#     #     speechRecognizer = speechsdk.SpeechRecognizer(speech_config=speechConfig, audio_config=audioConfig)
#     #
#     #     speechRecognizer.recognizing.connect(lambda evt: print('Recongizing: {}'.format(evt)))
#     #     speechRecognizer.recognized.connect(lambda evt: self.onRecognized(evt, block_dict))
#     #     speechRecognizer.session_started.connect(self.onSpeechStart)
#     #     #speechRecognizer.session_stopped.connect(lambda evt: print('Session stopped: {}'.format(evt)))
#     #     speechRecognizer.session_stopped.connect(lambda evt: self.onSpeechStop(evt, speechRecognizer, block_dict))
#     #     #speechRecognizer.canceled.connect(lambda evt: print('Canceled: {}').format(evt));
#     #     speechRecognizer.canceled.connect(lambda evt: self.onSpeechStop(evt, speechRecognizer, block_dict))
#     #     speechRecognizer.start_continuous_recognition_async()
#     #
#     #     while not block_dict['done']:
#     #         print("WAIT", len(block_dict['blockArray']))
#     #         time.sleep(0.5)
#     #
#     #     return block_dict
#
#     # def run(self):
#     #     print('running')
#     def __call__(self, *args, **kwargs):
#         with flask_app.app_context():
#             return self.run(*args, **kwargs)
#
#     # def run(self, *args, **kwargs):
#     #     print("L")

@celery_app.task()
def createBlockData(path):
    print("here")
    block_dict = {'blockArray': [], 'done': False}
    audioConfig = speechsdk.audio.AudioConfig(filename=path)
    speechRecognizer = speechsdk.SpeechRecognizer(speech_config=speechConfig, audio_config=audioConfig)

    speechRecognizer.recognizing.connect(lambda evt: print('Recongizing: {}'.format(evt)))
    speechRecognizer.recognized.connect(lambda evt: onRecognized(evt, block_dict))
    speechRecognizer.session_started.connect(onSpeechStart)
    #speechRecognizer.session_stopped.connect(lambda evt: print('Session stopped: {}'.format(evt)))
    speechRecognizer.session_stopped.connect(lambda evt: onSpeechStop(evt, speechRecognizer, block_dict))
    #speechRecognizer.canceled.connect(lambda evt: print('Canceled: {}').format(evt));
    speechRecognizer.canceled.connect(lambda evt: onSpeechStop(evt, speechRecognizer, block_dict))
    speechRecognizer.start_continuous_recognition_async()

    while not block_dict['done']:
        print("WAIT", len(block_dict['blockArray']))
        time.sleep(0.5)

    return block_dict

def genBlocks(result):
    global currentOffset, pauseThreshold, wordCountThreshold, emptyBlock
    blockArray = []

    print("generating blocks: ")
    words = json.loads(result.json)['NBest'][0]['Words'];
    print("words:", words)
    plainWords = result.text.split()
    print("plainwords: ", plainWords)
    block = emptyBlock.copy();
    print("block: ", block)

    for i in range(len(plainWords)):
        word = plainWords[i];
        wordOffset = words[i]['Offset'];
        if (wordOffset - currentOffset > pauseThreshold) or (plainWords[i][0].isupper() and len(block['text'].split()) > wordCountThreshold):
            block['duration'] = wordOffset - block['offset']
            blockArray.append(block.copy())
            block = emptyBlock.copy()
            block['offset'] = wordOffset;
            print("split: " + word)
        currentOffset = wordOffset
        block['text'] += word + " "
    block['duration'] = wordOffset - block['offset']
    blockArray.append(block.copy())

    print("block array: ", blockArray);
    return blockArray

@celery_app.task()
def CreateBlockDataFromWav(filepath):
    return json.dumps(createBlockData());


# @app.route('/')
# def hello():
#
#     return CreateBlockDataFromWav("data/bee movie.wav")
