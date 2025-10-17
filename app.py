from flask import Flask, request, jsonify
import os
import json
import logging
import requests
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# In-memory storage for tracking call-to-interview mapping
call_interview_mapping = {}

# --- YOUR EXISTING CONFIGURATION ---
AUTOMATE_SERVICE_URL = os.getenv('AUTOMATE_SERVICE_URL',
    'https://automate-profile-extraction-service-456784797908.us-central1.run.app/webhook')
AUTOMATE_WEBHOOK_SECRET = os.getenv('AUTOMATE_WEBHOOK_SECRET', 'supersecret123')
PROFILE_EXTRACTION_URL = os.getenv('PROFILE_EXTRACTION_URL', 'http://localhost:8080/process-interview')

# --- NEW: BACKEND API CONFIGURATION ---
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'https://ok-ai-backend-prod-36igu2sfua-uc.a.run.app/api')
JWT_TOKEN = os.getenv('JWT_TOKEN', '')

# --- UPDATED FUNCTIONS TO USE NEW API ENDPOINTS ---
def create_interview_record(user_id, language, call_id, interview_type):
    """Create an interview record using the new backend API"""
    try:
        url = f"{BACKEND_API_URL}/interviews"
        headers = {
            'Authorization': f'Bearer {JWT_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'userId': user_id,
            'language': language or 'en',
            'promptId': interview_type,
            'callID': call_id,
            'metadata': {
                'source': 'VAPI',
                'type': interview_type
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            data = response.json()
            # Handle different response structures
            interview_id = data.get('id') or data.get('interviewId')
            logging.info(f"Created interview record: {interview_id} for call {call_id}")
            return interview_id
        else:
            logging.error(f"Failed to create interview: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logging.error(f"Error creating interview: {str(e)}")
        return None

def create_transcript_record(interview_id, transcript_text, duration_ms):
    """Create transcript record using the new backend API"""
    try:
        url = f"{BACKEND_API_URL}/transcripts"
        headers = {
            'Authorization': f'Bearer {JWT_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        # Simple word splitting for the words array
        words = []
        word_list = transcript_text.split()
        current_time = 0
        for word in word_list:
            words.append({
                'word': word,
                'start': current_time,
                'end': current_time + 500
            })
            current_time += 500
        
        payload = {
            'interviewId': interview_id,
            'startMilliseconds': 0,
            'endMilliseconds': duration_ms or (len(word_list) * 500),
            'text': transcript_text,
            'words': words
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logging.info(f"Created transcript for interview {interview_id}")
            return True
        else:
            logging.error(f"Failed to create transcript: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Error creating transcript: {str(e)}")
        return False

def update_interview_status(interview_id, status):
    """Update interview status using the new backend API"""
    try:
        url = f"{BACKEND_API_URL}/interviews/{interview_id}"
        headers = {
            'Authorization': f'Bearer {JWT_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {'status': status}
        
        response = requests.put(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logging.info(f"Updated interview {interview_id} to status: {status}")
            return True
        else:
            logging.error(f"Failed to update interview: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Error updating interview: {str(e)}")
        return False

# --- YOUR EXISTING process_profile_locally FUNCTION - PRESERVED ---
def process_profile_locally(profile_data):
    """
    Local processing - logs data then forwards to the automation service webhook.
    """
    logging.info("Processing profile locally")
    logging.info(f"Profile data: {json.dumps(profile_data, indent=2)}")

    # Your original detailed logging is retained.
    logging.info(f"CallID: {profile_data.get('callId')}")
    logging.info(f"Phone: {profile_data.get('phoneNumber')}")
    logging.info(f"User ID: {profile_data.get('userId')}")
    logging.info(f"Customer Name: {profile_data.get('customerName')}")
    logging.info(f"Recording: {profile_data.get('recordingUrl')}")
    logging.info(f"Transcript length: {len(profile_data.get('transcript', ''))}")
    logging.info(f"Summary: {profile_data.get('summary')}")
    logging.info(f"Duration: {profile_data.get('duration')} seconds")
    logging.info(f"Platform: {profile_data.get('platform')}")
    logging.info(f"Interview Type: {profile_data.get('interviewType')}")

    headers = {
        'Content-Type': 'application/json',
        'x-webhook-secret': AUTOMATE_WEBHOOK_SECRET
    }
    
    try:
        logging.info(f"Sending to automation service: {AUTOMATE_SERVICE_URL}")

        response = requests.post(
            AUTOMATE_SERVICE_URL,
            json=profile_data,
            headers=headers,
            timeout=30
        )

        logging.info(f"Response status: {response.status_code}")

        if response.status_code == 200:
            logging.info("Successfully forwarded to automate service")
            try:
                response_data = response.json()
                logging.info(f"Automate service response: {json.dumps(response_data, indent=2)[:500]}")
            except:
                logging.info(f"Automate service response (text): {response.text[:500]}")
        else:
            logging.warning(f"Non-200 response from automate service: {response.status_code}")
            logging.warning(f"Response body: {response.text[:500]}")

    except requests.exceptions.Timeout:
        logging.error(f"Timeout forwarding to: {AUTOMATE_SERVICE_URL}")
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Connection error forwarding to {AUTOMATE_SERVICE_URL}: {str(e)}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error forwarding to {AUTOMATE_SERVICE_URL}: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error forwarding data to {AUTOMATE_SERVICE_URL}: {str(e)}")
        
    return True

@app.route('/webhook/vapi', methods=['POST'])
def handle_vapi_webhook():
    """
    Enhanced webhook handler with backend API integration
    """
    try:
        data = request.json
        message = data.get('message', {})
        message_type = message.get('type')

        logging.info(f"Received VAPI webhook: {message_type}")
        
        call_data = message.get('call', {})
        call_id = call_data.get('id')
        
        # Extract metadata
        assistant_data = message.get('assistant', {})
        metadata = assistant_data.get('metadata', {})
        
        # --- Handle status-update for interview creation ---
        if message_type == 'status-update':
            status = message.get('status')
            logging.info(f"Status update for call {call_id}: {status}")
            
            if status == 'in-progress' and call_id not in call_interview_mapping:
                user_id = metadata.get('userId')
                interview_type = metadata.get('interviewType', 'general')
                
                if user_id:
                    interview_id = create_interview_record(
                        user_id=user_id,
                        language='en',
                        call_id=call_id,
                        interview_type=interview_type
                    )
                    
                    if interview_id:
                        call_interview_mapping[call_id] = {
                            'interviewId': interview_id,
                            'userId': user_id,
                            'startTime': datetime.now().isoformat()
                        }
                        logging.info(f"Mapped call {call_id} to interview {interview_id}")
            
            return jsonify({'status': 'processed', 'type': message_type}), 200

        # --- Handle end-of-call-report ---
        if message_type != 'end-of-call-report':
            logging.info(f"Ignoring message type: {message_type}")
            return jsonify({'status': 'ignored', 'type': message_type}), 200

        # Extract metadata
        phone_number = metadata.get('customerPhone', 'unknown')
        user_id = metadata.get('userId')
        customer_name = metadata.get('customerName')

        logging.info(f"Found metadata - Phone: {phone_number}, Name: {customer_name}")
        
        # --- Handle backend API updates for end-of-call ---
        interview_id = None
        transcript = message.get('transcript', '')
        recording_url = message.get('recordingUrl', '')
        duration = message.get('durationSeconds', 0)
        duration_ms = int(duration * 1000) if duration else 0
        
        if call_id in call_interview_mapping:
            interview_id = call_interview_mapping[call_id]['interviewId']
            logging.info(f"Found existing interview {interview_id} for call {call_id}")
            
            # Create transcript
            if transcript and interview_id:
                create_transcript_record(interview_id, transcript, duration_ms)
            
            # Update interview to COMPLETED
            if interview_id:
                update_interview_status(interview_id, 'COMPLETED')
            
            del call_interview_mapping[call_id]

        # Profile payload
        profile_payload = {
            'callId': call_id,
            'interviewId': interview_id,
            'phoneNumber': phone_number,
            'userId': user_id,
            'customerName': customer_name,
            'transcript': transcript,
            'recordingUrl': recording_url,
            'summary': message.get('summary', ''),
            'endedReason': message.get('endedReason', ''),
            'cost': message.get('cost', 0),
            'duration': duration,
            'platform': metadata.get('platform', 'unknown'),
            'interviewType': metadata.get('interviewType', 'general')
        }

        logging.info(f"Processing call {call_id} for phone {phone_number}")
        logging.info(f"Customer name: {customer_name}")
        logging.info(f"Transcript length: {len(profile_payload['transcript'])} chars")
        logging.info(f"Recording URL: {profile_payload['recordingUrl']}")

        # Process
        if PROFILE_EXTRACTION_URL != 'http://localhost:8080/process-interview':
            try:
                response = requests.post(
                    PROFILE_EXTRACTION_URL,
                    json=profile_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                logging.info(f"Forwarded to {PROFILE_EXTRACTION_URL}, status: {response.status_code}")
            except Exception as e:
                logging.error(f"Error forwarding to extraction service: {str(e)}")
        else:
            process_profile_locally(profile_payload)

        return jsonify({'status': 'success', 'processed': True, 'interviewId': interview_id}), 200

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(f"Raw data: {json.dumps(request.json, indent=2)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- YOUR EXISTING process_interview ENDPOINT - PRESERVED ---
@app.route('/process-interview', methods=['POST'])
def process_interview():
    """
    The actual processing endpoint (receives filtered data)
    """
    try:
        data = request.json
        logging.info(f"Processing interview data for call: {data.get('callId')}")
        logging.info(f"Phone: {data.get('phoneNumber')}")
        logging.info(f"User ID: {data.get('userId')}")
        logging.info(f"Customer Name: {data.get('customerName')}")
        logging.info(f"Transcript preview: {data.get('transcript', '')[:200]}...")
        logging.info(f"Recording: {data.get('recordingUrl')}")
        logging.info(f"Duration: {data.get('duration')} seconds")
        logging.info(f"Summary: {data.get('summary')}")

        return jsonify({
            'status': 'success',
            'message': 'Interview processed',
            'callId': data.get('callId'),
            'phoneNumber': data.get('phoneNumber')
        }), 200

    except Exception as e:
        logging.error(f"Error in process-interview: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- YOUR EXISTING health ENDPOINT - ENHANCED ---
@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    """
    secret_preview = f"{AUTOMATE_WEBHOOK_SECRET[:4]}..." if AUTOMATE_WEBHOOK_SECRET else "Not Set"
    active_calls = len(call_interview_mapping)
    return jsonify({
        'status': 'healthy',
        'service': 'vapi-webhook-processor',
        'active_calls': active_calls,
        'endpoints': [
            '/webhook/vapi',
            '/process-interview',
            '/health'
        ],
        'config': {
            'profile_extraction_url': PROFILE_EXTRACTION_URL,
            'automate_service_url': AUTOMATE_SERVICE_URL,
            'automate_webhook_secret_set': secret_preview,
            'backend_api_url': BACKEND_API_URL,
            'jwt_configured': bool(JWT_TOKEN)
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
