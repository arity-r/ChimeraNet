
import os
import io
import tarfile
import zipfile
import numpy as np
import librosa
import soundfile

class AudioLoader:
    def __init__(self):
        pass
    def __del__(self):
        pass
    def load_audio(self, index, sr):
        return self._load_audio(index, sr)
    def _load_audio(self, index, sr):
        return None
    def __len__(self):
        return 0
    def __getitem__(self, key):
        parent = self
        if type(key) == int:
            p_index = [key]
        elif type(key) == tuple:
            p_index = key
        elif type(key) == slice:
            p_index = list(range(*key.indices(len(parent))))
        elif type(key) == np.ndarray:
            p_index = key
        else:
            raise TypeError(type(key), 'not supported')
        class _MiniLoader(AudioLoader):
            def _load_audio(self, index, sr):
                return parent._load_audio(p_index[index], sr)
            def __len__(self):
                return len(p_index)
        return _MiniLoader()

class FakeAudioLoader(AudioLoader):
    def __init__(self, n_samples, audio_size):
        super().__init__()
        self.n_samples = n_samples
        self.audio_size = audio_size
    def _load_audio(self, index, sr):
        return np.full(self.audio_size, index)
    def __len__(self):
        return self.n_samples

class Combiner(AudioLoader):
    def __init__(self, *loaders):
        super().__init__()
        self.loaders = loaders
        self.idx_to_idx = np.cumsum([len(l) for l in loaders])
    def _load_audio(self, index, sr):
        idx = np.searchsorted(self.idx_to_idx, index, 'right')
        midx = index - (0 if idx == 0 else self.idx_to_idx[idx-1])
        return self.loaders[idx].load_audio(midx, sr)
    def __len__(self):
        return self.idx_to_idx[-1]

def split_loader(loader, weights, shuffle=True):
    weights = np.array(weights)
    weights = weights / np.sum(weights)
    # TODO check dims of weights
    ranges = np.hstack(((0,), np.cumsum(weights*len(loader)))).astype(int)
    index = np.arange(len(loader))
    if shuffle:
        np.random.shuffle(index)
    return [loader[index[a:b]] for a, b in zip(ranges[:-1], ranges[1:])]

class DirAudioLoader(AudioLoader):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.sorted_file_list = sorted(os.listdir(path))
    def _load_audio(self, index, sr):
        y, _ = librosa.core.load(
            os.path.join(self.path, self.sorted_file_list[index]),
            sr=sr
        )
        return y
    def __len__(self):
        return len(self.sorted_file_list)

class ZipAudioLoader(AudioLoader):
    def __init__(self, zippath, path):
        super().__init__()
        self.zippath = zippath
        self.path = path
        zf = zipfile.ZipFile(zippath)
        self.name_list = list(
            i.filename for i in zf.infolist()
            if i.filename.startswith(path) and not i.is_dir()
        )
        zf.close()
    def __del__(self):
        super().__del__()
    def _load_audio(self, index, sr):
        zf = zipfile.ZipFile(self.zippath)
        b = zf.read(self.name_list[index])
        data, samplerate = soundfile.read(io.BytesIO(b))
        zf.close()
        return librosa.resample(librosa.to_mono(data.T), samplerate, sr)
    def __len__(self):
        return len(self.name_list)

class TarAudioLoader(AudioLoader):
    def __init__(self, tarpath, path):
        super().__init__()
        self.tarpath = tarpath
        self.path = path
        tf = tarfile.open(tarpath)
        self.name_list = list(
            i.name for i in self.tf.getmembers()
            if i.name.startswith(path) and i.isfile()
        )
        tf.close()
    def __del__(self):
        super().__del__()
    def load_audio(self, index, sr):
        tf = tarfile.open(self.tarpath)
        with self.tf.extractfile(self.name_list[index]) as f:
            data, samplerate = soundfile.read(f)
        tf.close()
        return librosa.resample(librosa.to_mono(data.T), samplerate, sr)
    def __len__(self):
        return len(self.name_list)
