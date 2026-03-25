import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: Number(__ENV.VUS || 4),
  duration: __ENV.DURATION || '45s',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<1200'],
  },
};

const baseUrl = (__ENV.CANARY_BASE_URL || 'http://ai-reliability-canary.ai-lab.svc.cluster.local:8080').replace(/\/$/, '');
const topK = Number(__ENV.TOP_K || 3);
const generativeRatio = Math.max(0, Math.min(1, Number(__ENV.GENERATIVE_RATIO || 0)));

const extractiveQuestions = [
  'What does the validation workflow enforce before merge?',
  'What operational value did the Trivy and smoke-test notes describe?',
  'What does the observability baseline say about service indicators?',
  'What did the guestbook readiness drill teach us about rolling updates?',
];

const generativeQuestions = [
  'Summarize how this repo treats reliability and QA before merge.',
  'What are the expected outcomes of the AI internal application failure drill?',
  'Explain why GitOps recovery is emphasized over live patching in the drills.',
];

function pickQuestion(questions) {
  return questions[Math.floor(Math.random() * questions.length)];
}

export default function () {
  const useGenerative = generativeRatio > 0 && Math.random() < generativeRatio;
  const mode = useGenerative ? 'generative' : 'extractive';
  const question = useGenerative ? pickQuestion(generativeQuestions) : pickQuestion(extractiveQuestions);

  const payload = JSON.stringify({
    question,
    top_k: topK,
    mode,
  });

  const response = http.post(`${baseUrl}/ask`, payload, {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '15s',
    tags: {
      target: 'canary',
      mode,
      source: 'analysis-burst',
    },
  });

  check(response, {
    'status is 2xx': (candidate) => candidate.status >= 200 && candidate.status < 300,
  });

  sleep(0.1);
}
