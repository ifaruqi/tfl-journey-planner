# TfL Journey Planner

A Streamlit web application for planning journeys across London using the Transport for London (TfL) Unified API.

## Features

- Smart Search: Autocomplete for stations, landmarks, postcodes, and addresses
- Multiple Routes: Compare different journey options
- Flexible Timing: Plan for now, departure time, or arrival time
- Accessibility: Option for step-free access routes
- Multi-Modal: Support for tube, bus, DLR, Overground, Elizabeth Line, and more

## Setup

### 1. Get TfL API Key

Register for a free API key at: https://api-portal.tfl.gov.uk/

### 2. Deploy to Streamlit Cloud

1. Fork/clone this repository
2. Go to share.streamlit.io
3. Connect your GitHub repository
4. Add your API key in Secrets (in the deployment settings)
5. Deploy!

### 3. Run Locally

Install dependencies:
pip install -r requirements.txt

Set your API key:
export TFL_APP_KEY="your_api_key_here"

Run the app:
streamlit run tfl_journey_planner.py

## Usage

1. Type your origin location (minimum 2 characters)
2. Select from the suggestions
3. Choose your destination
4. Set your travel preferences
5. Click Find Routes

## Technologies

- Streamlit: Web framework
- TfL Unified API: Real-time transport data
- Python Requests: API calls

## License

MIT License - Feel free to use and modify!
