import { lazy, Suspense, useState } from 'react';
import { FiCopy } from 'react-icons/fi';

const SyntaxHighlighter = lazy(async () => {
  const [highlighter, style] = await Promise.all([
    import('react-syntax-highlighter'),
    import('react-syntax-highlighter/dist/esm/styles/prism'),
  ]);
  return {
    default: (props) => (
      <highlighter.Prism {...props} style={style.vscDarkPlus} />
    ),
  };
});

const LANGUAGE_MAP = {
  python: { name: 'Python', ext: 'py' },
  javascript: { name: 'JavaScript', ext: 'js' },
  js: { name: 'JavaScript', ext: 'js' },
  typescript: { name: 'TypeScript', ext: 'ts' },
  ts: { name: 'TypeScript', ext: 'ts' },
  java: { name: 'Java', ext: 'java' },
  cpp: { name: 'C++', ext: 'cpp' },
  'c++': { name: 'C++', ext: 'cpp' },
  c: { name: 'C', ext: 'c' },
  csharp: { name: 'C#', ext: 'cs' },
  cs: { name: 'C#', ext: 'cs' },
  php: { name: 'PHP', ext: 'php' },
  ruby: { name: 'Ruby', ext: 'rb' },
  go: { name: 'Go', ext: 'go' },
  rust: { name: 'Rust', ext: 'rs' },
  swift: { name: 'Swift', ext: 'swift' },
  kotlin: { name: 'Kotlin', ext: 'kt' },
  scala: { name: 'Scala', ext: 'scala' },
  sql: { name: 'SQL', ext: 'sql' },
  html: { name: 'HTML', ext: 'html' },
  css: { name: 'CSS', ext: 'css' },
  bash: { name: 'Bash', ext: 'sh' },
  shell: { name: 'Shell', ext: 'sh' },
  json: { name: 'JSON', ext: 'json' },
  yaml: { name: 'YAML', ext: 'yml' },
  yml: { name: 'YAML', ext: 'yml' },
  markdown: { name: 'Markdown', ext: 'md' },
  md: { name: 'Markdown', ext: 'md' },
};

function getLanguageInfo(lang) {
  return LANGUAGE_MAP[String(lang || '').toLowerCase()] || { name: lang, ext: lang };
}

export default function LazySyntaxHighlightedCode({ code, language = 'python' }) {
  const [copied, setCopied] = useState(false);
  const langInfo = getLanguageInfo(language);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  return (
    <div className="bg-gray-900 dark:bg-gray-800 rounded-xl my-4 overflow-hidden border border-gray-700 dark:border-gray-600 shadow-lg">
      <div className="flex items-center justify-between px-3 sm:px-4 py-2 sm:py-3 bg-gray-800 dark:bg-gray-700 border-b border-gray-700 dark:border-gray-600">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-red-500" />
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-yellow-500" />
            <div className="w-2 h-2 sm:w-3 sm:h-3 rounded-full bg-green-500" />
          </div>
          <span className="text-xs text-gray-400 dark:text-gray-500 font-mono ml-1 sm:ml-2">
            {langInfo.name}
          </span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-300 dark:text-gray-500 dark:hover:text-gray-400 transition-colors px-2 py-1 rounded-lg hover:bg-gray-700 dark:hover:bg-gray-600"
        >
          <FiCopy size={12} />
          <span className="hidden sm:inline">{copied ? 'Copied!' : 'Copy'}</span>
        </button>
      </div>
      <div className="overflow-x-auto">
        <div className="p-3 sm:p-4">
          <Suspense
            fallback={
              <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap animate-pulse">
                Loading code view…
              </pre>
            }
          >
            <SyntaxHighlighter
              language={language.toLowerCase()}
              customStyle={{
                margin: 0,
                padding: 0,
                fontSize: '0.75rem',
                lineHeight: '1.4',
                backgroundColor: 'transparent',
                minWidth: '100%',
              }}
              showLineNumbers={false}
              wrapLines
              wrapLongLines
            >
              {code}
            </SyntaxHighlighter>
          </Suspense>
        </div>
      </div>
    </div>
  );
}
