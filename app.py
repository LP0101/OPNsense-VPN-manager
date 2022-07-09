from flask import Flask, request, jsonify, make_response, render_template
import json
import random
import requests
import urllib3
from os import getenv
import datetime


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

credentials = (getenv('OPNSENSE_USERNAME'), getenv('OPNSENSE_PASSWORD'))
opnsense_host = getenv('OPNSENSE_HOST', 'https://192.168.10.1')

alias_names = [
"MTL_MANAGED_VPN",
"NYC_MANAGED_VPN",
"NL_MANAGED_VPN",
]

VPN_NAMES = [
"Canada"
"USA"
"Netherlands"
]

def apply_alias(alias): 
    alias['alias']['content'] = "\n".join(alias['alias']['content'])
    uuid = get_uuid(alias['alias']['name'])
    requests.post(f"{opnsense_host}/api/firewall/alias/setItem/{uuid}", auth=credentials, verify=False, json=alias).content

def set_aliases():
    print(requests.post(f"{opnsense_host}/api/firewall/alias/set", auth=credentials, verify=False).content)

def get_uuid(alias):
    return requests.get(f"{opnsense_host}/api/firewall/alias/getAliasUUID/{alias}", auth=credentials, verify=False).json()["uuid"]

def get_current_aliases():
    current_aliases = {}
    for alias in alias_names:
        alias_uuid = get_uuid(alias)
        alias_json = requests.get(f"https://192.168.100.1/api/firewall/alias/getItem/{alias_uuid}", auth=credentials, verify=False).json()
        content = []
        for key in alias_json['alias']['content']:
            if key.startswith("192.168."):
                content.append(key)
        description = alias_json['alias']['description']
        current_aliases[alias] = {}
        current_aliases[alias]['alias'] = {}
        current_aliases[alias]['alias']["content"] = content
        current_aliases[alias]['alias']["description"] = description
        current_aliases[alias]['alias']["name"] = alias
        current_aliases[alias]['alias']['enabled'] = '1'
        current_aliases[alias]['alias']['counters'] = '0'
        current_aliases[alias]['alias']['interface'] = ''
        current_aliases[alias]['alias']['proto'] = ''
        current_aliases[alias]['alias']['updatefreq'] = ''
        current_aliases[alias]['alias']['type'] = 'host'
        current_aliases[alias]['network_content'] = ''
    return current_aliases

def add_ip(ip, alias): 
    current_alias = get_current_aliases()[alias]
    current_alias['alias']['content'].append(ip)
    apply_alias(current_alias)



def purge_ip(ip):
    aliases = get_current_aliases()
    for name, alias in aliases.items():
        if ip in alias['alias']['content']:
            print(alias)
            print(f"INFO :: Found active connection for {ip} in {name}. Deleting...")
            alias['alias']['content'].remove(ip)
        apply_alias(alias)

def get_active_vpn(ip): 
    aliases = get_current_aliases()
    current_vpn = "none"
    found = False

    for alias in aliases.values():
        if ip in alias['alias']['content']:
            if found:
                print("ERROR :: IP found in multiple lists, fixing status...")
                purge_ip(ip)
                current_vpn = "none"
                break
            current_vpn = alias
            found = True
    return current_vpn


@app.route('/active_vpn', methods=["GET"])
def get_vpn():
    if "X-Real-IP" in request.headers:
        ip = request.headers["X-Real-IP"]
    else:
        ip = request.remote_addr
    
    current_vpn = get_active_vpn(ip)
    return jsonify({"vpn": current_vpn})


@app.route('/activate_vpn', methods=["POST"])
def use_vpn():
    if "X-Real-IP" in request.headers:
        ip = request.headers["X-Real-IP"]
    else:
        ip = request.remote_addr

    print(f"INFO :: Making sure {ip} is not currently active...")
    purge_ip(ip)
    input_json = request.get_json(force = True)
    alias = input_json["vpn"]
    if alias != "none":
        add_ip(ip, alias)
        print(f"INFO :: Using {alias} for {ip}")
    else:
        print(f"INFO :: Disabling VPN for {ip}")
    set_aliases()
    return make_response(jsonify({}), 200)


@app.route('/', methods=["GET"])
def index():
    if "X-Real-IP" in request.headers:
        ip = request.headers["X-Real-IP"]
    else:
        ip = request.remote_addr
    
    active = get_active_vpn(ip)
    if isinstance(active, dict):
        active = active["alias"]["name"]
        # Make this nicer pls
        if active == "NYC_MANAGED_VPN": active = "USA"
        if active == "MTL_MANAGED_VPN": active = "Canada"
        if active == "NL_MANAGED_VPN": active = "NL"
    else: active = "None"
    
    return render_template("index.html", ip=ip, active=active)