import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

export function MarkdownRenderer({ content }: { content: string }) {
  return (
    // Code blocks stay dark in both themes (matches .terminal). Body text
    // inherits shell tokens so it stays readable when the theme flips.
    <div className="max-w-none text-shell-foreground">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
