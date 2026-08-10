"use client";

import { motion } from "framer-motion";
import { Archive, Check, Code2, Download, File, FileText, Image as ImageIcon, ShieldCheck, TriangleAlert } from "lucide-react";
import { fileKind, formatBytes } from "@/lib/format";
import type { FileResult } from "@/lib/ui-types";

const icons = { image: ImageIcon, pdf: FileText, archive: Archive, code: Code2, file: File };

export function FileCard({ file }: { file: FileResult }) {
  const Icon = icons[fileKind(file.name, file.mime)];
  return (
    <motion.article className={`file-card ${file.status}`} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      {/* Blob and data URLs arrive at runtime and cannot use Next image optimization. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {file.imageUrl ? <img className="file-preview" src={file.imageUrl} alt={`Preview of ${file.name}`} /> : null}
      <div className="file-card-main">
        <span className="file-icon"><Icon /></span>
        <span className="file-details"><strong title={file.name}>{file.name}</strong><small>{formatBytes(file.size)}</small></span>
        {file.status === "ready" && file.url ? (
          <motion.a whileTap={{ scale: 0.94 }} className="file-download" href={file.url} download={file.name} aria-label={`Download ${file.name}`}><Download /></motion.a>
        ) : null}
      </div>
      {file.status === "transferring" ? (
        <div className="transfer-block">
          <div className="transfer-copy"><span>Receiving from your PC</span><strong>{file.percent}%</strong></div>
          <div className="transfer-track"><motion.i animate={{ width: `${file.percent}%` }} /></div>
          <small>{file.receivedChunks} of {file.totalChunks} secure chunks</small>
        </div>
      ) : null}
      {file.status === "ready" ? (
        <div className={`checksum ${file.checksum}`}>
          {file.checksum === "verified" ? <><ShieldCheck /> Transfer verified</> : file.checksum === "mismatch" ? <><TriangleAlert /> Checksum mismatch</> : <><Check /> Ready on this device</>}
        </div>
      ) : null}
      {file.status === "error" ? <div className="file-error"><TriangleAlert /> {file.error || "Transfer failed"}</div> : null}
    </motion.article>
  );
}
