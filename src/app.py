#!/usr/bin/env python3

from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def main():
    return '''
     <form action="/plan" method="POST">
         <label>Start address:</label>
         <input name="start_address">
         <br/>
         <label>Transfer address:</label>
         <input name="transfer_address">
         <br/>
         <label>Destination address:</label>
         <input name="destination_address">
         <br/>
         <label>Drive mode:</label>
         <label><input type="radio" name="drive_mode" value="first" checked> First</label>
         <label><input type="radio" name="drive_mode" value="second"> Second</label>
         <br/>
         <input type="submit" value="Plan">
     '''

@app.route("/plan", methods=["POST"])
def plan():
    return '''
     <p>Planning in process</p>
     <form method="GET" action="/plan">
         <input type="submit" value="Refresh">
     </form>
     '''

@app.route("/plan", methods=["GET"])
def plan_refresh():
    return '''
     <p>Planning in process</p>
     <form method="GET" action="/plan">
         <input type="submit" value="Refresh">
     </form>
     '''