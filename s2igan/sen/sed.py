from typing import List

import torch
from torch import nn

class SpeechEncoder(nn.Module):
    def __init__(
        self,
        input_dim: int = 40,
        cnn_dim: List[int] = [64, 128],
        kernel_size: int = 6,
        stride: int = 2,
        rnn_dim: int = 512,
        rnn_num_layers: int = 2,
        rnn_type: str = "gru",
        rnn_dropout: float = 0.1,
        rnn_bidirectional: bool = True,
        attn_heads: int = 1,
        attn_dropout: float = 0.1,
    ):
        super().__init__()
        assert rnn_type in ["lstm", "gru"]
        self.cnn_1 = nn.Sequential(
            nn.Conv1d(input_dim, cnn_dim[0], 7 , stride),
            nn.BatchNorm1d(cnn_dim[0]),
            nn.SiLU(),
            nn.Conv1d(cnn_dim[0], 1024, 5 , stride),
            nn.BatchNorm1d(1024),
            nn.SiLU()
        )
        self.cnn_2 = nn.Sequential(
            nn.Conv1d(1024, cnn_dim[1], 7 , stride),
            nn.BatchNorm1d(cnn_dim[1]),
            nn.SiLU(), 
            nn.Conv1d(cnn_dim[1], 512, 5 , stride),
            nn.BatchNorm1d(512),
            nn.SiLU(), 
        )

        self.kernel_size = kernel_size
        self.stride = stride

        rnn_kwargs = dict(
            input_size=512,
            hidden_size=rnn_dim,
            num_layers=rnn_num_layers,
            batch_first=True,
            dropout=rnn_dropout,
            bidirectional=rnn_bidirectional,
        )
        if rnn_type == "lstm":
            self.rnn = nn.LSTM(**rnn_kwargs)
        else:
            self.rnn = nn.GRU(**rnn_kwargs)
        self.output_dim = rnn_dim * (int(rnn_bidirectional) + 1)
        self.self_attention = nn.MultiheadAttention(
            embed_dim=self.output_dim,
            num_heads=attn_heads,
            dropout=attn_dropout,
            batch_first=True,
        )
        self.feed_forward = nn.Sequential(
            nn.Linear(self.output_dim, self.output_dim*2),
            nn.Linear(self.output_dim*2, self.output_dim*4),
            nn.SiLU(),
            nn.Linear(self.output_dim*4, self.output_dim),
        )

    def get_params(self):
        return [p for p in self.parameters() if p.requires_grad]

    def forward(self, mel_spec, mel_spec_len):
        """
        mel_spec (-1, 40, len)
        output (-1, len, rnn_dim * (int(bidirectional) + 1))
        """
        cnn_out = self.cnn_1(mel_spec)
        cnn_out = self.cnn_2(cnn_out)

        # l = [
        #     torch.div(y - self.kernel_size, self.stride, rounding_mode="trunc") + 1
        #     for y in mel_spec_len
        # ]R
        # l = [
        #     torch.div(y - self.kernel_size, self.stride, rounding_mode="trunc") + 1
        #     for y in l
        # ]

        cnn_out = cnn_out.permute(0, 2, 1)

        # packed = pack_padded_sequence(
        #     cnn_out, l, batch_first=True, enforce_sorted=False
        # )
        # self.rnn.flatteSn_parameters()
        # out, hidden_state = self.rnn(packed)
        # out, seq_len = pad_packed_sequence(out, batch_first=True)
        # pack input before RNN to reduce computing efforts
        out, hidden_state = self.rnn(cnn_out)

        out, weights = self.self_attention(out, out, out)
        out = out.mean(dim=1)  
        out = torch.nn.functional.normalize(out)
        out = self.feed_forward(out)
        return out
    