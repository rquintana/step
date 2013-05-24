#!/usr/bin/env python

import os

import pygst
pygst.require('0.10')
import gst


__all__ = [ "Recognizer", "Listener" ]


MODEL_HOME = os.path.join(os.getcwd(), "adapted-model")

class Recognizer(object):
    """Simple ASR daemon."""

    def __init__(self):
        """Initialize the recognizer object."""
        self.__init_gst()
        self.__init_listeners_queue()

    def __init_gst(self):
        """Initialize the speech components."""
        self.__pipeline = gst.parse_launch('gconfaudiosrc ! audioconvert ! audioresample '
                                         + '! vader name=vad auto-threshold=true '
                                         + '! pocketsphinx name=asr ! fakesink')
        asr = self.__pipeline.get_by_name('asr')
        
        asr.set_property('hmm', os.path.join(MODEL_HOME, "default-model", "adapted")) 
        asr.set_property('lm', os.path.join(MODEL_HOME, "lm", "step-14.lm.DMP"))
        asr.set_property('dict', os.path.join(MODEL_HOME, "step-14.dic")) 
        asr.set_property('configured', True)
        
        asr.connect('partial_result', self.__asr_partial_result)
        asr.connect('result', self.__asr_result)

        bus = self.__pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.__application_message)

        self.__pipeline.set_state(gst.STATE_PLAYING)

    def __init_listeners_queue(self):
        """Initialize the event to handlers map."""
        self.__listeners = { "asr::result-ready" : [] }

    def __asr_partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def __asr_result(self, asr, text, uttid):
        """Forward result signals on the bus to the main thread."""
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        asr.post_message(gst.message_new_application(asr, struct))

    def __application_message(self, bus, msg):
        """Receive application messages from the bus."""
        msgtype = msg.structure.get_name()
        if msgtype == 'partial_result':
            self.__partial_result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'result':
            self.__final_result(msg.structure['hyp'], msg.structure['uttid'])

    def __partial_result(self, hyp, uttid):
        pass

    def __final_result(self, hyp, uttid):
        """
        Send the final result to the registered listeners for the
        asr::result-ready event.
        """
        self.__asr_pause()
        params = { "text" : hyp, "uttid" : uttid }
        
        for listener in self.__listeners["asr::result-ready"]:
            listener.handle(params)

        self.__asr_resume()
    
    def add_result_listener(self, listener):
        """Add a listener for the asr::result-ready event."""
        if listener is not None:
            self.__listeners["asr::result-ready"].append(listener)

    def clear_listeners(self, event_name=""):
        if self.__listeners.has_key(event_name):
            self.__listeners[event_name] = []
    
    def __asr_pause(self):
        """Pause the ASR daemon."""
        vader = self.__pipeline.get_by_name('vad')
        vader.set_property('silent', True)
        self.__pipeline.set_state(gst.STATE_PAUSED)

    def __asr_resume(self):
        """Resume the ASR daemon."""
        self.__pipeline.set_state(gst.STATE_PLAYING)


class Listener(object):
    """Define a listener interface for events generated by the Recognizer object."""

    def handle(self, params):
        """Handler for the emitted event."""
        raise NotImplementedError("Abstract method handle not implemented")