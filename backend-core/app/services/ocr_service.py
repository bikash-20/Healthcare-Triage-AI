import os
import re
from google.cloud import vision

client = None

def init_client():
  global client
  if client is None:
    client = vision.ImageAnnotatorClient()


def extract_text_from_image(path: str) -> str:
  init_client()
  with open(path, 'rb') as f:
    content = f.read()
  image = vision.Image(content=content)
  response = client.document_text_detection(image=image)
  if response.error.message:
    raise Exception(response.error.message)
  return response.full_text_annotation.text


def extract_vitals_from_text(raw_text: str) -> dict:
  text = raw_text.lower()
  numbers = {}

  patterns = {
    'bp': r'(?:bp|blood pressure)[:\s]*([0-9]{2,3}\/[0-9]{2,3})',
    'spo2': r'(?:spo2|sp[o0]2|oxygen saturation)[:\s]*([0-9]{2,3})',
    'temp': r'(?:temp|temperature)[:\s]*([0-9]{2,3}(?:\.[0-9])?)',
    'hr': r'(?:hr|heart rate|pulse)[:\s]*([0-9]{2,3})',
    'glucose': r'(?:glucose|blood sugar)[:\s]*([0-9]{2,4})'
  }

  for key, pattern in patterns.items():
    match = re.search(pattern, text)
    if match:
      value = match.group(1).strip()
      numbers[key] = value

  # If no BP pattern exists, look for standalone pressure text
  if 'bp' not in numbers:
    match = re.search(r'([0-9]{2,3}\/[0-9]{2,3})', text)
    if match:
      numbers['bp'] = match.group(1)

  return numbers


def parse_medical_text(raw_text: str) -> dict:
  extracted = {'raw_text': raw_text, 'auto_fill': extract_vitals_from_text(raw_text)}
  return extracted
