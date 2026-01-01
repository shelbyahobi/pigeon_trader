import requests
import json

def test_honeypot():
    # Test with a known token (e.g. Wrapped BNB or a big token like PEPE)
    token = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c" # WBNB
    url = f"https://api.honeypot.is/v2/IsHoneypot?address={token}&chainID=56"
    
    print(f"Testing URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print("Raw Response:")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_honeypot()
