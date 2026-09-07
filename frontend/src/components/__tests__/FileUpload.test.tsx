import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import FileUpload from '../FileUpload';

function makeFile(name: string, size = 1024, type = 'text/plain'): File {
  return new File([new ArrayBuffer(size)], name, { type });
}

function renderUpload(onUploaded = vi.fn(), onError = vi.fn(), disabled = false) {
  return render(
    <FileUpload onUploaded={onUploaded} onError={onError} disabled={disabled} />,
  );
}

describe('FileUpload', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('renders drop zone with correct text', () => {
    renderUpload();
    expect(screen.getByText(/Drag & drop or click to browse/i)).toBeTruthy();
    expect(screen.getByText(/PDF, DOCX, TXT/i)).toBeTruthy();
  });

  it('changes visual state on drag over', () => {
    const { container } = renderUpload();
    const dropzone = container.querySelector('#file-upload-dropzone')!;
    fireEvent.dragOver(dropzone);
    expect(screen.getByText('Drop to upload')).toBeTruthy();
  });

  it('reverts visual state on drag leave', () => {
    const { container } = renderUpload();
    const dropzone = container.querySelector('#file-upload-dropzone')!;
    fireEvent.dragOver(dropzone);
    fireEvent.dragLeave(dropzone);
    expect(screen.getByText(/Drag & drop or click to browse/i)).toBeTruthy();
  });

  it('shows selected file info after file selection via input', () => {
    const { container } = renderUpload();
    const input = container.querySelector('#file-upload-input')!;
    fireEvent.change(input, { target: { files: [makeFile('report.txt')] } });
    expect(screen.getByText('report.txt')).toBeTruthy();
  });

  it('calls onError for invalid file extension', () => {
    const onError = vi.fn();
    const { container } = renderUpload(vi.fn(), onError);
    const input = container.querySelector('#file-upload-input')!;
    fireEvent.change(input, { target: { files: [makeFile('virus.exe')] } });
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('Unsupported format'));
  });

  it('calls onError for file exceeding size limit', () => {
    const onError = vi.fn();
    const { container } = renderUpload(vi.fn(), onError);
    const oversized = makeFile('large.txt', 30 * 1024 * 1024);
    const input = container.querySelector('#file-upload-input')!;
    fireEvent.change(input, { target: { files: [oversized] } });
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('File too large'));
  });

  it('drops a valid file and shows it selected', () => {
    const { container } = renderUpload();
    const dropzone = container.querySelector('#file-upload-dropzone')!;
    const file = makeFile('doc.pdf');
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });
    expect(screen.getByText('doc.pdf')).toBeTruthy();
  });

  it('shows uploading state after clicking upload', async () => {
    const fetchMock = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal('fetch', fetchMock);

    const { container } = renderUpload();
    const input = container.querySelector('#file-upload-input')!;
    fireEvent.change(input, { target: { files: [makeFile('test.txt')] } });

    fireEvent.click(screen.getByText('Upload & Analyze'));
    expect(screen.getByText('Uploading…')).toBeTruthy();
    expect(screen.getByText('10%')).toBeTruthy();

    vi.unstubAllGlobals();
  });

  it('calls onUploaded after successful upload', async () => {
    const docResponse = {
      document_id: 'doc-123',
      filename: 'test.txt',
      mime_type: 'text/plain',
      page_count: 3,
      char_count: 1500,
      text_preview: 'Test content...',
      pages: [],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(docResponse),
    });
    vi.stubGlobal('fetch', fetchMock);

    const onUploaded = vi.fn();
    const { container } = renderUpload(onUploaded);
    const input = container.querySelector('#file-upload-input')!;
    fireEvent.change(input, { target: { files: [makeFile('test.txt')] } });

    fireEvent.click(screen.getByText('Upload & Analyze'));
    act(() => { vi.advanceTimersByTime(1000); });

    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledWith(docResponse);
    });

    vi.unstubAllGlobals();
  });

  it('calls onError when upload fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 413,
      statusText: 'Payload Too Large',
      json: () => Promise.resolve({ detail: 'File exceeds server limit' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const onError = vi.fn();
    const { container } = renderUpload(vi.fn(), onError);
    const input = container.querySelector('#file-upload-input')!;
    fireEvent.change(input, { target: { files: [makeFile('test.txt')] } });

    fireEvent.click(screen.getByText('Upload & Analyze'));
    act(() => { vi.advanceTimersByTime(1000); });

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(expect.stringContaining('File exceeds server limit'));
    });

    vi.unstubAllGlobals();
  });

  it('allows removing selected file', () => {
    const { container } = renderUpload();
    const input = container.querySelector('#file-upload-input')!;
    fireEvent.change(input, { target: { files: [makeFile('test.txt')] } });
    expect(screen.getByText('test.txt')).toBeTruthy();

    const removeBtn = screen.getByLabelText('Remove selected file');
    fireEvent.click(removeBtn);
    expect(screen.queryByText('test.txt')).toBeNull();
  });

  it('disables interactions when disabled prop is true', () => {
    renderUpload(vi.fn(), vi.fn(), true);
    const btn = screen.getByText('Upload & Analyze');
    expect(btn).toBeDisabled();
  });
});
