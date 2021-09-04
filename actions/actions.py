# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import AllSlotsReset, SlotSet

from jsonpath_ng import jsonpath, parse

import json
import requests
import http.client

def readBotenConfig():
    with open("botenConfig.json", "r") as f:
        data = json.load(f)
    return data


data = readBotenConfig()
intent = ""
parameters_array = []

class SetIntentAction(Action):
    def name(self) -> Text:
        return "action_set_intent"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        global intent 
        intent = tracker.latest_message['intent'].get('name').split("_", 2)[2]
        return []

class DefaultParametersAction(Action):
    def name(self) -> Text:
        return "action_set_default"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slots = []
        for parameter in data['default']:
            print(parameter)
            print(data['default'][parameter])
            slots.append(SlotSet(parameter, data['default'][parameter]))
        return slots

class AutoLocationAction(Action):
    def name(self) -> Text:
        return "action_auto_location"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slots = []
        location = str(tracker.get_slot('auto_latitude')) + ',' + str(tracker.get_slot('auto_longitude'))
        latitude = str(tracker.get_slot('auto_latitude'))
        longitude = str(tracker.get_slot('auto_longitude'))
        if(data['auto']['latitude,longitude']!=""):
            slots.append(SlotSet(data['auto']['latitude,longitude'], location))
        if(data['auto']['latitude']!=""):
            slots.append(SlotSet(data['auto']['latitude'], latitude))       
        if(data['auto']['longitude']!=""):
            slots.append(SlotSet(data['auto']['longitude'], longitude))
        print('latitude is ' + latitude + ', longitude is ' + longitude)
        # send utter default response to user
        dispatcher.utter_message(text='Your latitude is ' + latitude + ', longitude is ' + longitude)
        return slots

class FindSoltAction(Action):
    def name(self) -> Text:
        return "action_slots_values"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        global intent
        output = ''
        try:
            intent = tracker.latest_message['intent'].get('name').split("_", 2)[2]
            for parameters in data[intent]['parameters']:
                if(tracker.get_slot(parameters['name']) != None):
                    output += '- ' + parameters['name'] + ': ' + \
                        tracker.get_slot(parameters['name']) + '\n'
        except Exception as e:
            print(e)
        # send utter default response to user
        dispatcher.utter_message(text=output)
        return[]


class ApiAction(Action):
    def name(self) -> Text:
        return "action_use_api"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        global intent
        slots_dict = dict()
        try:
            intent = tracker.latest_message['intent'].get('name').split("_", 2)[2]
        except Exception as e:
            print(e)
        # Processing flow
        if(data[intent].__contains__('flow')):
            for flow in data[intent]['flow']:
                # Processing getSlots and get requests
                try:
                    for getSlots in flow['getSlots']:
                        if(getSlots['type'] == 'Single'):
                            resp = myRequests(
                                tracker, flow['intent'], getSlots['parameterName'], slots_dict[getSlots['parameterName']][0])
                            utter_text = determinalStatusCode(
                                resp, flow['intent'])
                            dispatcher.utter_message(text=utter_text)
                        else:
                            for slot_value in slots_dict[getSlots['parameterName']]:
                                resp = myRequests(
                                    tracker, flow['intent'], getSlots['parameterName'], slot_value)
                                utter_text = determinalStatusCode(
                                    resp, flow['intent'])
                                dispatcher.utter_message(text=utter_text)
                except Exception as e:
                    print(e)
                    resp = myRequests(tracker, flow['intent'], None, None)
                    utter_text = determinalStatusCode(resp, flow['intent'])
                    dispatcher.utter_message(text=utter_text)

                # Processing responseToSlots
                try:
                    for responseToSlots in flow['responseToSlots']:
                        jsonpath_expression = parse(
                            responseToSlots['jsonPath'])
                        emp_ids_list = [match.value for match in jsonpath_expression.find(
                            json.loads(resp.text))]
                        slots_dict[responseToSlots['parameterName']
                                   ] = emp_ids_list
                        print(slots_dict)
                except Exception as e:
                    print(e)

        # Processing path
        else:
            resp = myRequests(tracker, intent, None, None)
            utter_text = determinalStatusCode(resp, intent)
            dispatcher.utter_message(text=utter_text)
        return[]


def myRequests(tracker, intent, slot, slot_value):
    params = dict()
    url = data['url'] + data[intent]['pathName']
    # Processing parameters to params
    try:
        for parameters in data[intent]['parameters']:
            if(parameters['name'] != slot):
                if(parameters['in'] == 'path'):
                    try:
                        url = data['url'] + data[intent]['pathName'].split("{")[0] + tracker.get_slot(
                            parameters['name']) + data[intent]['pathName'].split("{")[1].split("}")[1]
                    except:
                        print("not has path params")
                elif(parameters['in'] == 'query'):
                    params[parameters['name']] = tracker.get_slot(
                        parameters['name'])
            # Processing response to slot
            else:
                if(parameters['in'] == 'path'):
                    try:
                        url = data['url'] + data[intent]['pathName'].split(
                            "{")[0] + str(slot_value) + data[intent]['pathName'].split("{")[1].split("}")[1]
                    except:
                        print("not has path params")
                elif(parameters['in'] == 'query'):
                    params[parameters['name']] = slot_value
    except KeyError:
        print(data[intent] + "'s parameters is unknown.")
    print(url)
    return requests.get(url=url, params=params)


def determinalStatusCode(resp, intent):
    # Determine whether the status code is OK
    if(resp.ok):
        resp_data = json.loads(resp.text)
        print(resp_data)
        return parseJsonPath(intent, resp_data)
    else:
        status_message = dict()
        print(resp.status_code)
        status_message['message'] = str(
            resp.status_code) + ": " + http.client.responses[resp.status_code]
        json_string = json.dumps(
            status_message, ensure_ascii=False).encode('utf8')
        return json_string.decode()


def parseJsonPath(intent, res):
    reslut = dict()
    thead_array = []
    tbody_array = []
    # Processing x-bot-jsonpPath-result
    for result_value in data[intent]['x-bot-jsonpPath-result']['result']:
        thead_array.append(result_value['title'])
        jsonpath_expression = parse(result_value['jsonPath'])
        emp_ids_list = [match.value for match in jsonpath_expression.find(res)]
        item = data[intent]['x-bot-jsonpPath-result']['item']
        tbody_array.append(emp_ids_list[:item])
    reslut['thead'] = thead_array
    reslut['tbody'] = tbody_array
    # dict to string
    json_string = json.dumps(reslut, ensure_ascii=False).encode('utf8')
    return json_string.decode()

class SlotReset(Action):
    def name(self) -> Text:
        return "action_reset_slot"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [AllSlotsReset()]