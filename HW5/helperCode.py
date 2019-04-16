# Run the ryu rest controller application
# then need to run the network in mininet
# sudo python NetRunnerNS.py -f  ./exampleNets/FINAL_NWD.JSON -ip 192.168.56.1
# 
# I ran the following code into my Jupyter notebook before I programmed the switches
# since there is a difference between DPID as a number and as a string name.
#
# Let's get info on the Switches:
import requests
r = requests.get("http://127.0.0.1:8080/stats/switches")  
dpids = r.json()  # Gets DPIDs as a list of integers, but we only know them by name.
# Let's create a map from switch name to data path ids (dpid)
name_id = {}
for dpid in dpids:
    my_bytes = (dpid).to_bytes(4, 'big') # Break integer into bytes
    name = my_bytes.decode('utf8').lstrip('\x00') # Convert bytes to UTF-8 string w/o junk
    name_id[name] = dpid
    
print(name_id)