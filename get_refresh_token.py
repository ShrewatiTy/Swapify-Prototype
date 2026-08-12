from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    print("Refresh token (save this as GOOGLE_REFRESH_TOKEN):", creds.refresh_token)
    with open('gmail_creds.json', 'w') as f:
        json.dump({
            "client_id": flow.client_config['client_id'],
            "client_secret": flow.client_config['client_secret'],
            "refresh_token": creds.refresh_token
        }, f)
    print("Saved gmail_creds.json")

if __name__ == '__main__':
    main()
