import ReactMarkdown from "react-markdown";

export function MarkdownText({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={{
        a: ({ children: label, ...props }) => <a {...props} target="_blank" rel="noreferrer">{label}</a>,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
