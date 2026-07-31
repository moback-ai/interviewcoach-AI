import assert from 'assert';
import {
  mapStructuredMessages,
  parseHistoryContent,
} from '../../utils/chatHistoryParse.js';

function testParseKeepsColonsInsideAssistantBody() {
  const blob = [
    'user:what is a vector database?',
    'assistant:A vector database stores embeddings.',
    '',
    '**Key point**: they support similarity search.',
    'For example: nearest-neighbor lookup is common.',
    'They are optimized for fast searches.',
  ].join('\n');

  const conversation = parseHistoryContent(blob);
  assert.strictEqual(conversation.length, 2);
  assert.strictEqual(conversation[0].speaker, 'candidate');
  assert.strictEqual(conversation[1].speaker, 'interviewer');
  assert.ok(conversation[1].message.includes('**Key point**:'));
  assert.ok(conversation[1].message.includes('For example:'));
  assert.ok(conversation[1].message.includes('optimized for fast searches'));
}

function testStructuredMessagesMapRoles() {
  const conversation = mapStructuredMessages([
    { role: 'user', content: 'hello', created_at: '2026-07-30T10:00:00Z' },
    {
      role: 'assistant',
      content: 'Hi.\n**Note**: stay on topic.',
      created_at: '2026-07-30T10:00:01Z',
    },
  ]);
  assert.strictEqual(conversation.length, 2);
  assert.strictEqual(conversation[0].speaker, 'candidate');
  assert.strictEqual(conversation[1].speaker, 'interviewer');
  assert.ok(conversation[1].message.includes('**Note**:'));
}

testParseKeepsColonsInsideAssistantBody();
testStructuredMessagesMapRoles();
console.log('chatHistoryParse tests passed');
