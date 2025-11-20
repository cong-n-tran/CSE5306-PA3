import requests

def get_leader():
    """
    Queries the local raft sidecar for the current leader.
    """
    try:
        r = requests.get("http://raft:50051/leader")
        return r.json().get("leader")
    except:
        return None
