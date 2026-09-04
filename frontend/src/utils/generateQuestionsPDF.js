const normalizeLevel = (level) => {
  const normalized = String(level || '').trim().toLowerCase();
  if (['beginner', 'easy', 'basic', 'junior', 'novice', 'simple'].includes(normalized)) return 'easy';
  if (['intermediate', 'medium', 'mid', 'moderate', 'coding'].includes(normalized)) return 'medium';
  if (['expert', 'hard', 'advanced', 'senior', 'difficult', 'complex'].includes(normalized)) return 'hard';
  return normalized || 'medium';
};

const hasSampleAnswer = (answer) => {
  const text = String(answer || '').trim();
  return Boolean(text) && text !== 'No answer provided';
};

const LEVEL_SECTION_LABELS = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };

/**
 * Client-side PDF export for an interview question set.
 * @param {Object} opts
 * @param {Array}  opts.questionsList  – items with { question, level, answer, missing }
 * @param {number|string} opts.questionSet
 * @param {string} [opts.jobTitle]
 */
export default function generateQuestionsPDF({ questionsList, questionSet, jobTitle }) {
  return import('jspdf').then(({ default: jsPDF }) => {
    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.width;
    const pageHeight = doc.internal.pageSize.height;
    const margin = 20;
    const maxWidth = pageWidth - 2 * margin;
    let y = 30;

    const ensureSpace = (needed = 20) => {
      if (y + needed > pageHeight - 25) {
        doc.addPage();
        y = 30;
      }
    };

    const writeWrapped = (text, options = {}) => {
      const {
        fontSize = 10,
        fontStyle = 'normal',
        color = [44, 62, 80],
        lineHeight = 5.5,
        indent = 0,
      } = options;
      doc.setFontSize(fontSize);
      doc.setFont('helvetica', fontStyle);
      doc.setTextColor(...color);
      const lines = doc.splitTextToSize(String(text || ''), maxWidth - indent);
      lines.forEach((line) => {
        ensureSpace(lineHeight + 2);
        doc.text(line, margin + indent, y);
        y += lineHeight;
      });
    };

    doc.setProperties({
      title: `Interview Questions — Set ${questionSet}`,
      subject: 'Generated interview questions',
      author: 'Interview Coach Platform',
      creator: 'Interview Coach Platform',
    });

    doc.setFontSize(22);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(44, 62, 80);
    doc.text('Interview Questions', pageWidth / 2, y, { align: 'center' });
    y += 12;

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(52, 73, 94);
    doc.text(`Question Set ${questionSet}`, pageWidth / 2, y, { align: 'center' });
    y += 8;

    if (jobTitle) {
      doc.text(`Role: ${jobTitle}`, pageWidth / 2, y, { align: 'center' });
      y += 8;
    }

    doc.text(
      `Generated: ${new Date().toLocaleDateString()} · ${questionsList.length} question${questionsList.length === 1 ? '' : 's'}`,
      pageWidth / 2,
      y,
      { align: 'center' },
    );
    y += 14;

    const byLevel = { easy: [], medium: [], hard: [] };
    questionsList.forEach((q) => {
      const level = normalizeLevel(q.level);
      if (byLevel[level]) byLevel[level].push(q);
      else byLevel.medium.push(q);
    });

    let globalIndex = 0;
    ['easy', 'medium', 'hard'].forEach((level) => {
      const items = byLevel[level];
      if (!items.length) return;

      ensureSpace(24);
      doc.setFontSize(14);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(52, 73, 94);
      doc.text(`${LEVEL_SECTION_LABELS[level]} (${items.length})`, margin, y);
      y += 10;

      items.forEach((q) => {
        globalIndex += 1;
        ensureSpace(28);
        writeWrapped(`Q${globalIndex}. ${q.question || 'Untitled question'}`, {
          fontSize: 11, fontStyle: 'bold', color: [44, 62, 80], lineHeight: 6,
        });
        y += 3;

        if (!q.missing && hasSampleAnswer(q.answer)) {
          writeWrapped('Sample answer:', {
            fontSize: 9, fontStyle: 'bold', color: [52, 73, 94], lineHeight: 5, indent: 4,
          });
          writeWrapped(q.answer, {
            fontSize: 9, fontStyle: 'normal', color: [70, 70, 70], lineHeight: 5, indent: 4,
          });
        } else {
          writeWrapped('Sample answer: Not generated yet', {
            fontSize: 9, fontStyle: 'italic', color: [120, 120, 120], lineHeight: 5, indent: 4,
          });
        }
        y += 8;
      });

      y += 4;
    });

    const totalPages = doc.internal.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.setFont('helvetica', 'italic');
      doc.setTextColor(128, 128, 128);
      doc.text(`Page ${i} of ${totalPages}`, pageWidth / 2, pageHeight - 10, { align: 'center' });
      doc.text('Interview Coach Platform', pageWidth / 2, pageHeight - 5, { align: 'center' });
    }

    const fileName = `interview-questions-set-${questionSet}-${new Date().toISOString().split('T')[0]}.pdf`;
    doc.save(fileName);
  });
}
